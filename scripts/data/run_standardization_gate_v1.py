#!/usr/bin/env python3
"""Read-only STANDARDIZATION_GATE V1 for the existing frozen run artifacts."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_ID = os.environ['CDAT_RUN_ID']
ART = ROOT / f'runs/{RUN_ID}/artifacts'
DATASET = ART / 'unified_dataset.csv'
SCHEMA = ROOT / 'schemas/canonical_schema.json'
TASK_AUDIT = ART / 'task_type_standardization_v17_audit.json'
CHANNEL_AUDIT = ART / 'channel_standardization_v1_audit.json'
SCHOOL_DIFF = ART / 'dimension_review/school_standardization_final_diff_report.md'
STD_REVIEW = ART / 'standardization_review.json'
RULES = [ROOT / 'config/data/standardization_rules.yaml', ROOT / 'config/data/school_aliases.yaml', ROOT / 'config/dimensions/task_type/task_type_rules_frozen_v17.yaml', ROOT / 'config/dimensions/channel/channel_rules_frozen_v1.yaml']
DATE_REMEDIATION_RULES = ROOT / 'config/data/date_standardization_rules_v1_1.yaml'
DATE_HUMAN_REVIEW = ROOT / 'config/data/date_human_review_round1.json'
OUT = ROOT / 'quality'
VALID_SCHOOL_SPECIAL = {'NON_SCHOOL', 'UNKNOWN', 'NON_UNIVERSITY_ENTITY', 'UNRESOLVED'}
# UNRESOLVED is an ACTIVE approved non-ranking classification in the Frozen
# school aliases.  Only UNSTANDARDIZED remains a pending human mapping state.
PENDING_SCHOOL = {'UNSTANDARDIZED'}
VALID_TASK_STATUSES = {'STANDARDIZED', 'MULTI_TASK', 'EXCLUDED_BY_BUSINESS_RULE', 'UNKNOWN'}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle)), None


def valid_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def missing_marker(value: str) -> bool:
    return value.strip() in {'', '/', '-', '—', '未知', '无'}


def add_issue(items, category, severity, field, row, issue_type, required_fix, rule_reference):
    items.append({
        'category': category, 'severity': severity, 'field': field,
        'source_id': row.get('source_id', ''), 'source_row_id': row.get('source_row_id', ''),
        'affected_record': f"{row.get('source_id', '')}:{row.get('source_row_id', '')}",
        'current_value': row.get(field, ''), 'original_value': row.get(f'{field}_original', ''),
        'issue_type': issue_type, 'required_fix': required_fix, 'rule_reference': rule_reference
    })


def main():
    inputs = [DATASET, SCHEMA, TASK_AUDIT, CHANNEL_AUDIT, SCHOOL_DIFF, STD_REVIEW, *RULES, DATE_REMEDIATION_RULES, DATE_HUMAN_REVIEW]
    before = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
    rows, _ = read_rows(DATASET)
    headers = list(rows[0]) if rows else []
    schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
    expected = [f['name'] for f in schema['fields']]
    missing_fields = [f for f in expected if f not in headers]
    extra_fields = [f for f in headers if f not in expected]
    task_audit = json.loads(TASK_AUDIT.read_text(encoding='utf-8'))
    channel_audit = json.loads(CHANNEL_AUDIT.read_text(encoding='utf-8'))
    prior_review = json.loads(STD_REVIEW.read_text(encoding='utf-8'))
    approved_date_decisions = json.loads(DATE_HUMAN_REVIEW.read_text(encoding='utf-8'))['approved_decisions']
    issues = []

    # School: permitted special classifications are explicitly retained; pending
    # classifications require human mapping and are blocking at this Gate.
    school = Counter(r['school'] for r in rows)
    for row in rows:
        if row['school'] in PENDING_SCHOOL:
            add_issue(issues, 'school', 'BLOCKING', 'school', row, 'PENDING_HUMAN_SCHOOL_MAPPING', 'Approve a frozen canonical school mapping or an approved non-school/unknown classification; do not infer.', 'RULE-013; config/data/school_aliases.yaml')

    # Task/channel results are accepted only if their frozen audits pass and
    # the row statuses do not contain unapproved values.
    invalid_task_rows = [r for r in rows if r['task_type_standardization_status'] not in VALID_TASK_STATUSES]
    for row in invalid_task_rows:
        add_issue(issues, 'task_type', 'BLOCKING', 'task_type', row, 'INVALID_TASK_TYPE_STATUS', 'Return to frozen Task Type mapping governance.', 'task_type_rules_frozen_v17.yaml')
    invalid_channel_rows = [r for r in rows if r['channel_standardization_status'] != 'STANDARDIZED']
    for row in invalid_channel_rows:
        add_issue(issues, 'channel', 'BLOCKING', 'channel', row, 'INVALID_CHANNEL_STATUS', 'Return to frozen Channel mapping governance.', 'channel_rules_frozen_v1.yaml')

    # Date absence is not automatically invalid. An unparseable original value
    # which left the canonical date blank remains a blocking unresolved field.
    for field in ['consultation_date', 'ddl']:
        for row in rows:
            value, original = row[field].strip(), row[f'{field}_original'].strip()
            if value and not valid_date(value):
                add_issue(issues, 'date', 'BLOCKING', field, row, 'INVALID_ISO_DATE', 'Correct via an approved date rule or mark the original value with an explicit approved missing status.', 'RULE-002~RULE-006')
            elif not value and not missing_marker(original) and not (field == 'ddl' and original == '未定') and approved_date_decisions.get(f"{row['source_id']}:{row['source_row_id']}:{field}", {}).get('decision') != 'INVALID_DATE':
                add_issue(issues, 'date', 'BLOCKING', field, row, 'UNRESOLVED_DATE_TEXT', 'Approve an applicable frozen date rule or a documented missing classification.', 'RULE-002~RULE-006')

    # Amount blanks with a blank marker are valid missing. Other non-empty raw
    # values with no parsed amount are unresolved numeric fields.
    for row in rows:
        amount, original = row['amount_cny'].strip(), row['amount_original'].strip()
        if amount:
            try:
                float(amount)
            except ValueError:
                add_issue(issues, 'numeric', 'BLOCKING', 'amount_cny', row, 'INVALID_PARSED_AMOUNT', 'Correct via approved amount rule; gate cannot alter the value.', 'RULE-009; RULE-010')
        elif not missing_marker(original):
            add_issue(issues, 'numeric', 'BLOCKING', 'amount_cny', row, 'UNRESOLVED_NUMERIC_TEXT', 'Approve an amount parsing/missing classification through human rule governance.', 'RULE-009; RULE-010')

    # Header differences are schema blocking: the gate does not reinterpret the
    # additional columns or change the frozen schema.
    if missing_fields or extra_fields:
        issues.append({'category': 'schema', 'severity': 'BLOCKING', 'field': 'dataset_header', 'source_id': '', 'source_row_id': '', 'affected_record': 'ALL_DATASET_ROWS', 'current_value': '; '.join(extra_fields), 'original_value': '', 'issue_type': 'CANONICAL_SCHEMA_HEADER_MISMATCH', 'required_fix': 'Human-controlled schema/version alignment or a compliant standardized dataset header; gate must not rename/drop fields.', 'rule_reference': 'schemas/canonical_schema.json'})

    blocking = [x for x in issues if x['severity'] == 'BLOCKING']
    warnings = []
    for row in rows:
        if row['school'] in VALID_SCHOOL_SPECIAL or not row['school'].strip():
            warnings.append({'field': 'school', 'status': row['school'] or 'EMPTY', 'record': f"{row['source_id']}:{row['source_row_id']}"})
        if row['task_type_standardization_status'] == 'UNKNOWN':
            warnings.append({'field': 'task_type', 'status': 'UNKNOWN_EXPLICIT', 'record': f"{row['source_id']}:{row['source_row_id']}"})
        if not row['ddl'].strip() and (missing_marker(row['ddl_original'].strip()) or row['ddl_original'].strip() == '未定'):
            warnings.append({'field': 'ddl', 'status': 'VALID_MISSING', 'record': f"{row['source_id']}:{row['source_row_id']}"})
        if not row['amount_cny'].strip() and missing_marker(row['amount_original'].strip()):
            warnings.append({'field': 'amount_cny', 'status': 'VALID_MISSING', 'record': f"{row['source_id']}:{row['source_row_id']}"})

    # `warnings` here are explicit, approved observations (for example a
    # VALID_MISSING DDL or approved NON_SCHOOL classification).  They remain
    # visible to Data Quality but do not downgrade a fully standardized input.
    # Only future non-blocking *actionable* findings may produce
    # PASS_WITH_WARNINGS.
    actionable_warnings = []
    decision = 'FAIL' if blocking else ('PASS_WITH_WARNINGS' if actionable_warnings else 'PASS')
    school_pending = sum(school[x] for x in PENDING_SCHOOL)
    task_unknown = sum(1 for r in rows if r['task_type_standardization_status'] == 'UNKNOWN')
    unresolved_by_category = dict(Counter(x['category'] for x in blocking))
    rule_versions = {
        'canonical_schema': schema.get('schema_version'),
        'business_rules': schema.get('business_rules_version'),
        'task_type_rules': task_audit.get('rule_version'),
        'channel_rules': channel_audit.get('channel_rules_version'),
        'school_aliases': '1.1'
    }
    report = {
        'gate_name': 'STANDARDIZATION_GATE', 'gate_version': '1.0', 'run_id': RUN_ID,
        'dataset_version': schema.get('schema_version'), 'rule_versions': rule_versions,
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'school_status': {'status': 'FAIL' if school_pending else 'PASS', 'canonical_or_approved_special_rows': len(rows)-school_pending, 'pending_human_mapping_rows': school_pending, 'unresolved_rows': school['UNRESOLVED'], 'unstandardized_rows': school['UNSTANDARDIZED'], 'school_id_status': 'PRESENT_FOR_ROUND2_APPROVALS' if 'school_id' in headers and sum(1 for r in rows if r.get('school_rule_id') == 'RULE-013-HR2' and r.get('school_id')) == 3 else 'NOT_AVAILABLE_FOR_ROUND2_APPROVALS', 'evidence': 'school_standardization_final_diff_report.md'},
        'task_type_status': {'status': 'PASS' if task_audit['result']=='PASS' and not invalid_task_rows else 'FAIL', 'unknown_explicit_rows': task_unknown, 'unmatched_rows': task_audit['counts']['unmatched'], 'review_required_rows': task_audit['checks']['review_required_zero']['detail']['count'], 'evidence': 'task_type_standardization_v17_audit.json'},
        'channel_status': {'status': 'PASS' if channel_audit['result']=='PASS' and not invalid_channel_rows else 'FAIL', 'unmatched_rows': channel_audit['counts']['unmatched'], 'review_required_rows': channel_audit['counts']['review_required'], 'legal_null_secondary_channel_rows': channel_audit['counts']['legal_channel_null'], 'evidence': 'channel_standardization_v1_audit.json'},
        'date_status': {'status': 'FAIL' if unresolved_by_category.get('date', 0) else 'PASS_WITH_WARNINGS', 'blocking_unresolved_date_fields': unresolved_by_category.get('date', 0), 'valid_missing_ddl_rows': sum(1 for x in warnings if x['field']=='ddl'), 'consultation_date_valid_missing_rows': sum(1 for r in rows if not r['consultation_date'].strip() and missing_marker(r['consultation_date_original'].strip()))},
        'numeric_status': {'status': 'FAIL' if unresolved_by_category.get('numeric', 0) else 'PASS_WITH_WARNINGS', 'blocking_unresolved_numeric_fields': unresolved_by_category.get('numeric', 0), 'valid_missing_amount_rows': sum(1 for x in warnings if x['field']=='amount_cny')},
        'schema_status': {'status': 'FAIL' if missing_fields or extra_fields else 'PASS', 'missing_fields': missing_fields, 'extra_fields': extra_fields, 'expected_field_count': len(expected), 'actual_field_count': len(headers)},
        'human_review_status': {'historical_review_issue_count': prior_review['review_required_count'], 'current_blocking_issue_cells': len(blocking), 'current_blocking_unique_records': len({x['affected_record'] for x in blocking if x['affected_record'] != 'ALL_DATASET_ROWS'}), 'truly_remaining_manual_school_rows': school_pending, 'note': 'Historical review records are not automatically treated as current blockers; current final dataset values are rechecked above.'},
        'blocking_issue_count': len(blocking), 'warning_count': len(warnings), 'actionable_warning_count': len(actionable_warnings), 'decision': decision,
        'data_standardization_agent_final_status': 'HUMAN_REVIEW_REQUIRED' if decision == 'FAIL' else 'COMPLETED',
        'return_to_agent': 'Data Standardization Agent' if decision == 'FAIL' else None,
        'required_fixes': [{'field': c, 'record_count': n, 'issue_type': next(x['issue_type'] for x in blocking if x['category']==c), 'affected_records': [x['affected_record'] for x in blocking if x['category']==c][:25], 'required_fix': next(x['required_fix'] for x in blocking if x['category']==c), 'rule_reference': next(x['rule_reference'] for x in blocking if x['category']==c)} for c, n in sorted(unresolved_by_category.items())],
        'qa': {'dataset_checksum_unchanged': before[str(DATASET.relative_to(ROOT))] == sha(DATASET), 'frozen_rules_unchanged': all(before[str(p.relative_to(ROOT))] == sha(p) for p in [SCHEMA, *RULES]), 'gate_did_not_reinterpret_task_type': task_audit['result'] == 'PASS', 'gate_did_not_reinterpret_channel': channel_audit['result'] == 'PASS', 'issues_traceable': all(x['rule_reference'] and x['affected_record'] for x in issues)}
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'standardization_gate_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    fields = ['category','severity','field','source_id','source_row_id','affected_record','current_value','original_value','issue_type','required_fix','rule_reference']
    with (OUT / 'standardization_gate_issues.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        w = csv.DictWriter(handle, fieldnames=fields); w.writeheader(); w.writerows(issues)
    if not all(report['qa'].values()):
        raise RuntimeError('STANDARDIZATION_GATE QA failed')
    print(json.dumps({'decision': decision, 'blocking_issue_count': len(blocking), 'warning_count': len(warnings), 'by_category': unresolved_by_category}, ensure_ascii=False))


if __name__ == '__main__':
    main()
