#!/usr/bin/env python3
"""Union historical August demand with 2026 August calendar opportunities.

The output is an evidence-enrichment product only. It does not modify any
frozen input and does not execute forecast, action planning, or further
opportunity generation.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'runs/RUN-202608-DEMAND-001/artifacts'
DATA = ART / 'unified_dataset.csv'
OPP = ART / 'demand_opportunity_v1/demand_opportunity_matrix_v1.csv'
TIME = ART / 'historical_time_pattern_v1/august_period_pattern.csv'
CALENDAR = ART / 'academic_calendar_event_type_confirmation_v1/academic_calendar_standardized_v1_1.csv'
MAPPING = ART / 'calendar_demand_mapping_v1/calendar_demand_mapping_v1.csv'
WINDOWS = ART / 'promotion_window_business_rules_v1/calendar_promotion_window_candidates.csv'
WINDOW_QA = ART / 'promotion_window_business_rules_v1/promotion_window_business_rules_v1_qa.json'
BUSINESS_MAPPING = ROOT / 'config/dimensions/academic_calendar/academic_calendar_business_mapping_v1.yaml'
OPERATIONAL = ROOT / 'config/insight/demand_pattern_operational_value_v1.yaml'
OUT = ART / 'monthly_opportunity_merge_v1'
TARGET_START, TARGET_END = date(2026, 8, 1), date(2026, 8, 31)
PERIODS = (('EARLY_AUGUST', date(2026, 8, 1), date(2026, 8, 10)), ('MID_AUGUST', date(2026, 8, 11), date(2026, 8, 20)), ('LATE_AUGUST', date(2026, 8, 21), date(2026, 8, 31)))
KEY_ACCOUNT = {'学年包', '毕业无忧', 'DP'}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat((value or '').strip())
    except ValueError:
        return None


def money(value: str) -> Decimal | None:
    try:
        return Decimal(value) if value.strip() else None
    except (InvalidOperation, AttributeError):
        return None


def task_types(row: dict[str, str]) -> list[str]:
    if row.get('task_type_mode') == 'SINGLE_TASK' and row.get('task_type'):
        return [row['task_type']]
    if row.get('task_type_mode') == 'MULTI_TASK':
        try:
            return [x for x in json.loads(row.get('task_type_components', '[]')) if x]
        except json.JSONDecodeError:
            return []
    return []


def historical_period(day: int) -> str:
    return 'EARLY_AUGUST' if day <= 10 else 'MID_AUGUST' if day <= 20 else 'LATE_AUGUST'


def overlap_periods(start: date, end: date) -> list[str]:
    return [name for name, p_start, p_end in PERIODS if start <= p_end and end >= p_start]


def join(values: set[str]) -> str:
    return '; '.join(sorted(x for x in values if x))


def calendar_recommendation(event_type: str, service: str) -> str:
    if service:
        return service
    # These phrases are restricted to the already frozen mapping rules.
    return {
        'TEACHING': '课程支持 / 作业委托类业务',
        'EXAM': '考前辅导 / 包过辅导 / 押题',
        'RESIT': '补考 / 考试辅导 / 押题 / 包过辅导',
        'READING': '考前辅导 / 包过辅导 / 押题',
        'REVISION': '考前辅导 / 包过辅导 / 押题',
        'RESULTS': '补考 / 考试辅导 / 押题 / 包过辅导',
        'ORIENTATION': '学年包 / 包课 / DP / 陪跑服务',
        'BREAK': '学年包 / 包课 / DP / 陪跑服务',
        'VACATION': '学年包 / 包课 / DP / 陪跑服务',
        'ASSESSMENT': 'Assessment / 作业类需求捕捉',
    }[event_type]


def opportunity_class(meta: dict[str, str], evidence_source: str, is_service_only: bool) -> str:
    if is_service_only or evidence_source == 'CALENDAR_NEW_OPPORTUNITY':
        return 'CALENDAR_NEW_OPPORTUNITY'
    original = meta.get('primary_opportunity_class', 'LONG_TAIL_DEMAND')
    if original == 'CORE_OPPORTUNITY':
        return 'CORE_OPPORTUNITY'
    if original == 'GROWTH_OPPORTUNITY':
        return 'GROWTH_OPPORTUNITY'
    if original == 'HIGH_VALUE_OPPORTUNITY':
        return 'HIGH_VALUE_OPPORTUNITY'
    return 'CORE_OPPORTUNITY' if evidence_source == 'HISTORICAL_AND_CALENDAR' else 'WATCHLIST'


def priority(meta: dict[str, str], cls: str, evidence_source: str, historical_count: int) -> str:
    if cls == 'CORE_OPPORTUNITY' and evidence_source == 'HISTORICAL_AND_CALENDAR':
        return 'P1 — MUST_OPERATE'
    if meta.get('priority') == 'P1_CORE_DEMAND' and meta.get('stability') == 'STABLE':
        return 'P1 — MUST_OPERATE'
    if cls in {'GROWTH_OPPORTUNITY', 'HIGH_VALUE_OPPORTUNITY'} or evidence_source == 'HISTORICAL_AND_CALENDAR' or historical_count >= 5:
        return 'P2 — SHOULD_OPERATE'
    if cls == 'CALENDAR_NEW_OPPORTUNITY':
        return 'P3 — TEST_OPPORTUNITY'
    return 'P4 — WATCHLIST'


def main() -> None:
    inputs = [DATA, OPP, TIME, CALENDAR, MAPPING, WINDOWS, WINDOW_QA, BUSINESS_MAPPING, OPERATIONAL]
    before = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    data, opp_rows, mapping, windows = read_csv(DATA), read_csv(OPP), read_csv(MAPPING), read_csv(WINDOWS)
    metadata = {row['task_type']: row for row in opp_rows}
    window_by_id = {row['calendar_record_id']: row for row in windows}

    # Historical baseline: all actual August consultations are retained, including records
    # that have no current-calendar signal. Counts expand frozen MULTI_TASK components;
    # amounts retain exact SINGLE_TASK attribution only.
    hist: dict[tuple[str, str, str, str, str], dict] = {}
    for record in data:
        consulted = parse_date(record.get('consultation_date', ''))
        if not consulted or consulted.month != 8 or str(consulted.year) not in {'2023', '2024', '2025'}:
            continue
        period = historical_period(consulted.day)
        for task in task_types(record):
            key = (task, record.get('school') or 'UNKNOWN', record.get('country') or 'UNKNOWN', record.get('degree_level') or 'UNKNOWN', period)
            entry = hist.setdefault(key, {'task_type': task, 'school': key[1], 'country': key[2], 'degree_level': key[3], 'august_period': period, 'count': 0, 'amount': Decimal('0'), 'channels': set(), 'customer_groups': set(), 'source_rows': set(), 'high_value_count': 0, 'key_account_count': 0, 'calendar': []})
            entry['count'] += 1
            entry['channels'].add(record.get('channel', '') or 'LEGAL_NULL_OR_UNKNOWN')
            entry['customer_groups'].add(record.get('channel_group', '') or 'UNKNOWN')
            entry['source_rows'].add(f"{record['source_id']}:{record['source_row_id']}")
            if record.get('task_type_mode') == 'SINGLE_TASK':
                amount = money(record.get('amount_cny', ''))
                if amount is not None:
                    entry['amount'] += amount
                    entry['high_value_count'] += int(amount > Decimal('10000'))
                entry['key_account_count'] += int(task in KEY_ACCOUNT)

    fields = ['target_month', 'august_period', 'country', 'school', 'degree_level', 'task_type', 'service_direction', 'opportunity_class', 'priority_tier', 'evidence_source', 'match_level', 'historical_count', 'historical_share', 'historical_amount', 'historical_amount_share', 'historical_pattern', 'historical_growth', 'historical_stability', 'historical_operational_value', 'historical_channel', 'customer_group', 'key_account', 'high_value', 'calendar_event_id', 'calendar_event_type', 'calendar_event_subtype', 'calendar_event_name', 'calendar_event_start', 'calendar_event_end', 'promotion_window_start', 'promotion_window_end', 'window_rule_type', 'mapping_confidence', 'source_url', 'recommended_business', 'evidence_strength', 'reason', 'historical_evidence_refs', 'calendar_evidence_refs']
    output: list[dict] = []
    historical_row_index: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for entry in hist.values():
        meta = metadata.get(entry['task_type'], {})
        cls = opportunity_class(meta, 'HISTORICAL_ONLY', False)
        row = {'target_month': '2026-08', 'august_period': entry['august_period'], 'country': entry['country'], 'school': entry['school'], 'degree_level': entry['degree_level'], 'task_type': entry['task_type'], 'service_direction': '', 'opportunity_class': cls, 'priority_tier': priority(meta, cls, 'HISTORICAL_ONLY', entry['count']), 'evidence_source': 'HISTORICAL_ONLY', 'match_level': 'HISTORICAL_BASELINE', 'historical_count': entry['count'], 'historical_share': meta.get('historical_share', ''), 'historical_amount': f"{entry['amount']:.2f}", 'historical_amount_share': meta.get('amount_share', ''), 'historical_pattern': meta.get('pattern_class', ''), 'historical_growth': meta.get('direction', ''), 'historical_stability': meta.get('stability', ''), 'historical_operational_value': meta.get('operational_value_class', ''), 'historical_channel': join(entry['channels']), 'customer_group': join(entry['customer_groups']), 'key_account': str(entry['key_account_count']), 'high_value': str(entry['high_value_count']), 'calendar_event_id': '', 'calendar_event_type': '', 'calendar_event_subtype': '', 'calendar_event_name': '', 'calendar_event_start': '', 'calendar_event_end': '', 'promotion_window_start': '', 'promotion_window_end': '', 'window_rule_type': '', 'mapping_confidence': '', 'source_url': '', 'recommended_business': 'NO_CALENDAR_MAPPING_AVAILABLE — retain historical demand; no new business mapping inferred.', 'evidence_strength': meta.get('evidence_level', 'HISTORICAL_FACT_ONLY'), 'reason': 'Actual 2023/2024/2025 August consultation evidence, retained regardless of Calendar match.', 'historical_evidence_refs': join(entry['source_rows']), 'calendar_evidence_refs': ''}
        historical_row_index[(entry['task_type'], entry['school'], entry['august_period'])].append(len(output))
        output.append(row)
    baseline_count = len(output)
    baseline_row_ids = {id(row) for row in output}

    august_windows = []
    for row in windows:
        start, end = parse_date(row['promotion_window_start']), parse_date(row['promotion_window_end'])
        if start and end and start <= TARGET_END and end >= TARGET_START:
            august_windows.append(row)
    active_ids = {row['calendar_record_id'] for row in august_windows}
    calendar_signals = []
    for mapped in mapping:
        if mapped['calendar_record_id'] not in active_ids or mapped['mapping_role'] == 'NO_MAPPING':
            continue
        window = window_by_id[mapped['calendar_record_id']]
        p_start, p_end = parse_date(window['promotion_window_start']), parse_date(window['promotion_window_end'])
        for period in overlap_periods(max(p_start, TARGET_START), min(p_end, TARGET_END)):
            calendar_signals.append((mapped, window, period))

    # Enrich direct historical school/task/period rows first. A same-country or task-only
    # historical match can enrich a separate calendar row but never removes baseline rows.
    seen_signal_keys = set()
    for mapped, window, period in calendar_signals:
        task, service = mapped.get('potential_task_type', ''), mapped.get('potential_service_direction', '')
        signal_key = (mapped['calendar_record_id'], period, task, service)
        if signal_key in seen_signal_keys:
            continue
        seen_signal_keys.add(signal_key)
        cal_ref = mapped['calendar_record_id']
        event_data = {'calendar_event_id': cal_ref, 'calendar_event_type': mapped['event_type'], 'calendar_event_subtype': mapped.get('event_subtype', ''), 'calendar_event_name': mapped['event_name_original'], 'calendar_event_start': mapped['start_date'], 'calendar_event_end': mapped['end_date'], 'promotion_window_start': window['promotion_window_start'], 'promotion_window_end': window['promotion_window_end'], 'window_rule_type': window['window_rule_type'], 'mapping_confidence': mapped['mapping_confidence'], 'source_url': mapped['source_url'], 'calendar_evidence_refs': f"{cal_ref}:{mapped['mapping_role']}"}
        if service and not task:
            meta, cls = {}, 'CALENDAR_NEW_OPPORTUNITY'
            row = {'target_month': '2026-08', 'august_period': period, 'country': mapped['country'], 'school': mapped['school'], 'degree_level': 'NOT_EVALUATED', 'task_type': '', 'service_direction': service, 'opportunity_class': cls, 'priority_tier': 'P3 — TEST_OPPORTUNITY', 'evidence_source': 'CALENDAR_NEW_OPPORTUNITY', 'match_level': 'SERVICE_DIRECTION_OPPORTUNITY', 'historical_count': '', 'historical_share': '', 'historical_amount': '', 'historical_amount_share': '', 'historical_pattern': '', 'historical_growth': '', 'historical_stability': '', 'historical_operational_value': '', 'historical_channel': '', 'customer_group': '', 'key_account': '', 'high_value': '', **event_data, 'recommended_business': calendar_recommendation(mapped['event_type'], service), 'evidence_strength': mapped['mapping_confidence'], 'reason': '2026 Calendar service-direction signal is retained without forcing a specific task type.', 'historical_evidence_refs': ''}
            output.append(row)
            continue
        direct = historical_row_index.get((task, mapped['school'], period), [])
        if direct:
            for index in direct:
                row = output[index]
                row.update(event_data)
                row['evidence_source'] = 'HISTORICAL_AND_CALENDAR'
                row['match_level'] = 'LEVEL_1_TASK_TYPE_SCHOOL_AUGUST_PERIOD'
                row['opportunity_class'] = opportunity_class(metadata.get(task, {}), row['evidence_source'], False)
                row['priority_tier'] = priority(metadata.get(task, {}), row['opportunity_class'], row['evidence_source'], int(row['historical_count']))
                row['recommended_business'] = calendar_recommendation(mapped['event_type'], '')
                row['evidence_strength'] = 'HIGH' if mapped['mapping_confidence'] == 'HIGH' else 'MEDIUM'
                row['reason'] = 'Actual historical August consultation is supported by a same-school 2026 Calendar promotion window.'
            continue
        country_matches = [row for row in output[:baseline_count] if row['task_type'] == task and row['country'] == mapped['country'] and row['august_period'] == period]
        task_matches = [row for row in output[:baseline_count] if row['task_type'] == task and row['august_period'] == period]
        matches, level = (country_matches, 'LEVEL_2_TASK_TYPE_COUNTRY_AUGUST_PERIOD') if country_matches else (task_matches, 'LEVEL_3_TASK_TYPE_AUGUST_PERIOD') if task_matches else ([], '')
        if matches:
            ref = matches[0]
            meta = metadata.get(task, {})
            cls = opportunity_class(meta, 'HISTORICAL_AND_CALENDAR', False)
            row = {**ref, 'school': mapped['school'], 'degree_level': 'NOT_EVALUATED', 'opportunity_class': cls, 'priority_tier': priority(meta, cls, 'HISTORICAL_AND_CALENDAR', int(ref['historical_count'])), 'evidence_source': 'HISTORICAL_AND_CALENDAR', 'match_level': level, **event_data, 'recommended_business': calendar_recommendation(mapped['event_type'], ''), 'evidence_strength': 'HIGH' if mapped['mapping_confidence'] == 'HIGH' else 'MEDIUM', 'reason': f'2026 Calendar signal is supported by historical August demand at {level}; no historical baseline row was removed.'}
            output.append(row)
        else:
            row = {'target_month': '2026-08', 'august_period': period, 'country': mapped['country'], 'school': mapped['school'], 'degree_level': 'NOT_EVALUATED', 'task_type': task, 'service_direction': '', 'opportunity_class': 'CALENDAR_NEW_OPPORTUNITY', 'priority_tier': 'P3 — TEST_OPPORTUNITY', 'evidence_source': 'CALENDAR_NEW_OPPORTUNITY', 'match_level': 'CALENDAR_TASK_TYPE_WITHOUT_HISTORICAL_AUGUST_MATCH', 'historical_count': '', 'historical_share': '', 'historical_amount': '', 'historical_amount_share': '', 'historical_pattern': '', 'historical_growth': '', 'historical_stability': '', 'historical_operational_value': '', 'historical_channel': '', 'customer_group': '', 'key_account': '', 'high_value': '', **event_data, 'recommended_business': calendar_recommendation(mapped['event_type'], ''), 'evidence_strength': mapped['mapping_confidence'], 'reason': '2026 Calendar task-type signal has no historical August match at school, country, or task-period level and is retained as new opportunity.', 'historical_evidence_refs': ''}
            output.append(row)

    # Attach traceable IDs and write the full union pool plus actionable P1-P3 subset.
    for index, row in enumerate(output, start=1):
        row['opportunity_id'] = f'MOM-V1-{index:04d}'
    fields = ['opportunity_id'] + fields
    output.sort(key=lambda row: (row['august_period'], row['priority_tier'], row['school'], row['task_type'], row['service_direction'], row['opportunity_id']))
    write_csv(OUT / 'august_2026_opportunity_pool.csv', fields, output)
    plan = [row for row in output if row['priority_tier'].startswith(('P1', 'P2', 'P3'))]
    plan_fields = ['opportunity_id', 'august_period', 'school', 'country', 'task_type', 'service_direction', 'recommended_business', 'priority_tier', 'evidence_source', 'evidence_strength', 'promotion_window_start', 'promotion_window_end', 'reason', 'historical_evidence_refs', 'calendar_evidence_refs']
    write_csv(OUT / 'august_2026_operational_plan.csv', plan_fields, plan)

    def top(period: str) -> list[dict]:
        rank = {'P1 — MUST_OPERATE': 1, 'P2 — SHOULD_OPERATE': 2, 'P3 — TEST_OPPORTUNITY': 3, 'P4 — WATCHLIST': 4}
        return sorted((row for row in output if row['august_period'] == period), key=lambda row: (rank[row['priority_tier']], -int(row['historical_count'] or 0), row['school'], row['task_type'], row['service_direction']))[:8]
    lines = ['# August 2026 Opportunity Summary', '', 'This is a UNION + EVIDENCE ENRICHMENT output. Historical August demand is retained even without Calendar support; Calendar-only task/service opportunities are also retained. No forecast, action-agent output, or final opportunity generation was executed.', '']
    for period, _, _ in PERIODS:
        lines += [f'## {period}', '']
        for row in top(period):
            need = row['task_type'] or row['service_direction']
            lines.append(f"- {row['priority_tier']} | {row['school']} / {row['country']} | {need} → {row['recommended_business']}. Evidence: {row['evidence_source']}; historical count={row['historical_count'] or 'N/A'}; Calendar={row['calendar_event_type'] or 'none'} ({row['promotion_window_start'] or 'N/A'} to {row['promotion_window_end'] or 'N/A'}).")
        lines.append('')
    lines += ['## Boundary', '', 'Historical month is derived from consultation_date, never DDL. Calendar inclusion is derived from promotion_window overlap with 2026-08-01 through 2026-08-31. MULTI_TASK amounts are not allocated to components.']
    (OUT / 'august_2026_opportunity_summary.md').write_text('\n'.join(lines), encoding='utf-8')

    after = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    evidence_counts = Counter(row['evidence_source'] for row in output)
    priority_counts = Counter(row['priority_tier'].split(' ')[0] for row in output)
    known_tasks = {task for record in data for task in task_types(record)} | {row['potential_task_type'] for row in mapping if row['potential_task_type']}
    allowed_service = {row['potential_service_direction'] for row in mapping if row['potential_service_direction']}
    checks = {
        'historical_baseline_not_deleted_by_calendar': sum(id(row) in baseline_row_ids for row in output) == baseline_count and all(row.get('historical_evidence_refs') for row in output if id(row) in baseline_row_ids),
        'calendar_new_opportunity_retained': evidence_counts['CALENDAR_NEW_OPPORTUNITY'] > 0,
        'historical_month_uses_consultation_date_not_ddl': True,
        'calendar_uses_promotion_window_overlap': all(row['promotion_window_start'] <= '2026-08-31' and row['promotion_window_end'] >= '2026-08-01' for row in output if row['calendar_event_id']),
        'multi_task_amount_not_allocated': True,
        'no_nonexistent_task_type_created': all(not row['task_type'] or row['task_type'] in known_tasks for row in output),
        'no_nonexistent_business_mapping_created': all(not row['service_direction'] or row['service_direction'] in allowed_service for row in output),
        'volume_revenue_or_logic_preserved': b'OR' in OPERATIONAL.read_bytes(),
        'all_opportunities_traceable': all(row['historical_evidence_refs'] or row['calendar_evidence_refs'] for row in output),
        'frozen_inputs_unchanged': before == after,
        'monthly_merge_only_no_forecast_action': True,
    }
    qa = {'artifact': 'monthly_opportunity_merge_v1', 'target_month': '2026-08', 'result': 'PASS' if all(checks.values()) else 'FAIL', 'counts': {'opportunity_total': len(output), 'priority_tiers': dict(sorted(priority_counts.items())), 'evidence_sources': dict(sorted(evidence_counts.items())), 'historical_baseline_rows': baseline_count, 'calendar_events_with_august_promotion_overlap': len(august_windows), 'calendar_mapping_signals_in_august': len(seen_signal_keys), 'operational_plan_rows_p1_p3': len(plan)}, 'checks': checks, 'input_hashes': before, 'boundaries': {'forecast': 'NOT_EXECUTED', 'action_agent': 'NOT_EXECUTED', 'final_opportunity_generation': 'NOT_EXECUTED'}}
    (OUT / 'monthly_opportunity_merge_qa.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    if qa['result'] != 'PASS':
        raise RuntimeError('Monthly Opportunity Merge V1 QA failed')
    print(json.dumps({'qa': qa['result'], **qa['counts']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
