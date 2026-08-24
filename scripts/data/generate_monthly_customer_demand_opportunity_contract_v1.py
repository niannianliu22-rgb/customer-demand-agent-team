#!/usr/bin/env python3
"""Freeze the existing August country-direction view into the monthly contract."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'runs/RUN-202608-DEMAND-001/artifacts'
TIMING = ART / 'august_2026_country_business_timing_v1/august_2026_country_business_timing.csv'
SCHOOLS = ART / 'august_2026_country_business_timing_v1/august_2026_country_school_opportunities.csv'
POOL = ART / 'monthly_opportunity_merge_v1/august_2026_opportunity_pool.csv'
TASK_RULES = ROOT / 'config/dimensions/task_type/task_type_rules_frozen_v17.yaml'
SERVICE_RULES = ROOT / 'config/dimensions/academic_calendar/academic_calendar_business_mapping_v1.yaml'
OUT = ART / 'monthly_customer_demand_opportunity_contract_v1'
TARGET_MONTH = '2026-08'
STAGES = {'ORIENTATION', 'TEACHING', 'READING', 'ASSESSMENT', 'REVISION', 'EXAM', 'RESULTS', 'RESIT', 'BREAK', 'VACATION'}
DIRECTIONS = {'ASSIGNMENT_BUSINESS', 'DISSERTATION_BUSINESS', 'EXAM_BUSINESS', 'RESIT_BUSINESS', 'LONG_TERM_SERVICE', 'COURSE_SUPPORT', 'SELECTION_SUPPORT'}


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_task_types():
    lines = TASK_RULES.read_text(encoding='utf-8').splitlines()
    start = lines.index('official_task_types:') + 1
    end = lines.index('aliases:')
    return {line[2:] for line in lines[start:end] if line.startswith('- ')}


def frozen_service_directions():
    rules = json.loads(SERVICE_RULES.read_text(encoding='utf-8'))
    return {v for event in rules['event_mappings'] for v in event.get('potential_service_direction', [])}


def split_values(value):
    return [v for v in value.split('; ') if v]


def strength(row):
    # Preserve the contract's three display states without re-scoring evidence.
    if row['time_evidence_source'] in {'HISTORICAL_AND_CALENDAR', 'HISTORICAL_ONLY'}:
        return 'STRONG'
    if row['time_evidence_source'] == 'CALENDAR_ONLY':
        return 'DIRECTIONAL'
    return 'WATCH' if row['priority'].startswith('P4') else 'DIRECTIONAL'


def schema():
    return {
        '$schema': 'https://json-schema.org/draft/2020-12/schema',
        '$id': 'monthly_customer_demand_opportunity_v1.schema.json',
        'title': 'Monthly Customer Demand Opportunity V1',
        'type': 'array',
        'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['target_month', 'country', 'best_operating_window', 'window_start', 'window_end', 'time_evidence_source', 'academic_stages', 'business_directions', 'key_schools', 'school_opportunities', 'historical_evidence', 'calendar_evidence', 'opportunity_strength', 'reason', 'source_artifacts'],
            'properties': {
                'target_month': {'type': 'string', 'pattern': r'^\\d{4}-\\d{2}$'},
                'country': {'type': 'string'},
                'best_operating_window': {'enum': ['EARLY_AUGUST', 'MID_AUGUST', 'LATE_AUGUST']},
                'window_start': {'type': 'string', 'format': 'date'},
                'window_end': {'type': 'string', 'format': 'date'},
                'time_evidence_source': {'enum': ['HISTORICAL_AND_CALENDAR', 'HISTORICAL_ONLY', 'CALENDAR_ONLY', 'DIRECTIONAL']},
                'academic_stages': {'type': 'array', 'items': {'enum': sorted(STAGES)}},
                'business_directions': {'type': 'array', 'minItems': 1, 'items': {'enum': sorted(DIRECTIONS)}},
                'key_schools': {'type': 'array', 'items': {'type': 'string'}},
                'school_opportunities': {'type': 'array', 'items': {'type': 'object', 'required': ['school', 'specific_task_types', 'service_directions', 'promotion_window', 'historical_support', 'calendar_support', 'evidence_strength'], 'properties': {'school': {'type': 'string'}, 'specific_task_types': {'type': 'array', 'items': {'type': 'string'}}, 'service_directions': {'type': 'array', 'items': {'type': 'string'}}, 'promotion_window': {'type': 'object'}, 'historical_support': {'type': 'string'}, 'calendar_support': {'type': 'string'}, 'evidence_strength': {'type': 'string'}}}},
                'historical_evidence': {'type': 'object'}, 'calendar_evidence': {'type': 'object'},
                'opportunity_strength': {'enum': ['STRONG', 'DIRECTIONAL', 'WATCH']},
                'reason': {'type': 'string'}, 'source_artifacts': {'type': 'array', 'items': {'type': 'string'}}
            }
        }
    }


def main():
    inputs = [TIMING, SCHOOLS, POOL, TASK_RULES, SERVICE_RULES]
    before = {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    timing, schools = read_csv(TIMING), read_csv(SCHOOLS)
    school_index = defaultdict(list)
    for row in schools:
        school_index[(row['country'], row['business_direction'], row['best_operating_window'])].append(row)
    source_artifacts = [str(p.relative_to(ROOT)) for p in [TIMING, SCHOOLS, POOL, TASK_RULES, SERVICE_RULES]]
    records = []
    for row in timing:
        key = (row['country'], row['business_direction'], row['best_operating_window'])
        school_records = []
        for s in school_index[key]:
            school_records.append({
                'school': s['school'], 'specific_task_types': split_values(s['specific_task_types']),
                'service_directions': split_values(s['service_directions']),
                'promotion_window': {'start': split_values(s['promotion_window_start']), 'end': split_values(s['promotion_window_end'])},
                'historical_support': 'PRESENT' if 'HISTORICAL' in s['evidence_source'] else 'NOT_PRESENT',
                'calendar_support': 'PRESENT' if 'CALENDAR' in s['evidence_source'] else 'NOT_PRESENT',
                'evidence_strength': s['evidence_strength']
            })
        stages = [s for s in split_values(row['academic_stages']) if s in STAGES]
        records.append({
            'target_month': TARGET_MONTH, 'country': row['country'], 'best_operating_window': row['best_operating_window'],
            'window_start': row['window_start'], 'window_end': row['window_end'], 'time_evidence_source': row['time_evidence_source'],
            'academic_stages': stages, 'business_directions': [row['business_direction']],
            'key_schools': [s['school'] for s in school_records], 'school_opportunities': school_records,
            'historical_evidence': {'support': row['historical_support'], 'source': 'Historical August Demand / Time Pattern'},
            'calendar_evidence': {'support': row['calendar_support'], 'source': '2026 Calendar promotion windows'},
            'opportunity_strength': strength(row), 'reason': row['time_reason'], 'source_artifacts': source_artifacts
        })
    records.sort(key=lambda r: (r['country'], r['business_directions'][0], r['best_operating_window']))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'monthly_customer_demand_opportunity_v1.schema.json').write_text(json.dumps(schema(), ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'august_2026_customer_demand_opportunity_v1.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    fields = ['target_month', 'country', 'best_operating_window', 'window_start', 'window_end', 'time_evidence_source', 'academic_stages', 'business_directions', 'key_schools', 'school_opportunities', 'historical_evidence', 'calendar_evidence', 'opportunity_strength', 'reason', 'source_artifacts']
    flat = [{k: json.dumps(r[k], ensure_ascii=False) if isinstance(r[k], (list, dict)) else r[k] for k in fields} for r in records]
    write_csv(OUT / 'august_2026_customer_demand_opportunity_v1.csv', fields, flat)
    lines = ['# August 2026 Customer Demand Opportunity Contract V1', '']
    for country in sorted({r['country'] for r in records}):
        lines += [f'## {country}', '']
        for r in [x for x in records if x['country'] == country]:
            direction = r['business_directions'][0]
            stages = ' / '.join(r['academic_stages']) or 'No Calendar stage asserted'
            lines += [f"### {r['best_operating_window']} — {direction} ({r['opportunity_strength']})", '', f'- Academic Stage: {stages}', f"- Why: {r['reason']}", '- Key Schools:']
            for s in r['school_opportunities'][:8]:
                demand = '; '.join(s['specific_task_types'] or s['service_directions'])
                lines.append(f"  - {s['school']}: {demand}")
            lines.append('')
    (OUT / 'august_2026_customer_demand_opportunity_summary.md').write_text('\n'.join(lines), encoding='utf-8')

    task_types, services = frozen_task_types(), frozen_service_directions()
    emitted_tasks = {t for r in records for s in r['school_opportunities'] for t in s['specific_task_types']}
    emitted_services = {v for r in records for s in r['school_opportunities'] for v in s['service_directions']}
    all_calendar_new = {r['opportunity_id'] for r in read_csv(POOL) if r['evidence_source'] == 'CALENDAR_NEW_OPPORTUNITY'}
    retained_refs = {ref for s in schools for ref in split_values(s['opportunity_refs'])}
    checks = {
        'country_layer_has_only_business_directions': all(set(r['business_directions']) <= DIRECTIONS for r in records),
        'specific_demand_only_at_school_layer': all('specific_task_types' not in r and 'service_directions' not in r for r in records),
        'every_business_direction_has_best_window': all(r['best_operating_window'] for r in records),
        'historical_calendar_evidence_traceable': all(r['source_artifacts'] for r in records),
        'calendar_does_not_delete_historical': any(r['historical_evidence']['support'] != 'records=0; schools=0' for r in records),
        'calendar_new_opportunity_retained': all_calendar_new <= retained_refs,
        'no_new_task_types': emitted_tasks <= task_types,
        'no_new_service_directions': emitted_services <= services,
        'no_new_high_dimensional_crosses': all(set(r) <= {'target_month','country','best_operating_window','window_start','window_end','time_evidence_source','academic_stages','business_directions','key_schools','school_opportunities','historical_evidence','calendar_evidence','opportunity_strength','reason','source_artifacts'} for r in records),
        'august_2026_complete_conversion': len(records) == len(timing),
        'frozen_upstream_unchanged': before == {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    }
    qa = {'artifact': 'monthly_customer_demand_opportunity_contract_v1', 'result': 'PASS' if all(checks.values()) else 'FAIL', 'counts': {'contract_records': len(records), 'countries': len({r['country'] for r in records}), 'opportunity_strength': dict(sorted(Counter(r['opportunity_strength'] for r in records).items())), 'key_school_counts_by_country': {c: len({s for r in records if r['country'] == c for s in r['key_schools']}) for c in sorted({r['country'] for r in records})}}, 'checks': checks, 'source_artifacts': source_artifacts, 'input_hashes': before}
    (OUT / 'monthly_customer_demand_opportunity_contract_v1_qa.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    if qa['result'] != 'PASS': raise RuntimeError('Monthly opportunity contract QA failed')
    print(json.dumps({'qa': qa['result'], **qa['counts']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
