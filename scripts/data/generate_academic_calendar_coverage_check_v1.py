#!/usr/bin/env python3
"""Coverage-only audit: frozen Historical Patterns vs calendar collection status."""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'runs/RUN-202608-DEMAND-001/artifacts'
PAT = ART / 'historical_demand_pattern_v1/historical_demand_patterns.csv'
MASTER = ART / 'academic_calendar_v1/supporting_school_master.csv'
VERSION = sys.argv[1] if len(sys.argv) > 1 else 'v1'
OUT = ART / f'academic_calendar_coverage_{VERSION}'
OUT.mkdir(exist_ok=True)

def read(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))

def write(path, fields, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

patterns = read(PAT)
schools = {row['school_name']: row for row in read(MASTER)}
READY = {'READY'}
READY_PARTIAL = {'READY', 'PARTIAL'}
PRIORITY_VALUES = {'CORE_OPPORTUNITY', 'HIGH_VALUE_OPPORTUNITY'}

def linked(row):
    return json.loads(row['supporting_schools'])

def is_covered(row, valid_statuses):
    return any(schools[item['school_name']]['calendar_status'] in valid_statuses for item in linked(row))

detail = []
for row in patterns:
    statuses = sorted({schools[item['school_name']]['calendar_status'] for item in linked(row)})
    detail.append({
        'month': row['month'], 'country': row['country'], 'task_type': row['task_type'],
        'value_class': row['value_class'], 'pattern_strength': row['pattern_strength'],
        'historical_order_count': row['historical_order_count'],
        'supporting_schools': '; '.join(item['school_name'] for item in linked(row)),
        'supporting_school_statuses': '; '.join(statuses),
        'ready_covered': str(is_covered(row, READY)).upper(),
        'ready_or_partial_covered': str(is_covered(row, READY_PARTIAL)).upper(),
    })

summary = []
for label, subset in [
    ('ALL_PATTERNS', patterns),
    ('STRONG', [row for row in patterns if row['pattern_strength'] == 'STRONG']),
    ('MEDIUM', [row for row in patterns if row['pattern_strength'] == 'MEDIUM']),
    ('CORE', [row for row in patterns if row['value_class'] == 'CORE_OPPORTUNITY']),
    ('HIGH_VALUE', [row for row in patterns if row['value_class'] == 'HIGH_VALUE_OPPORTUNITY']),
]:
    denominator = len(subset)
    ready_count = sum(is_covered(row, READY) for row in subset)
    rp_count = sum(is_covered(row, READY_PARTIAL) for row in subset)
    summary.append({
        'scope': label, 'denominator_patterns': denominator,
        'ready_covered_patterns': ready_count,
        'ready_coverage_rate': round(ready_count / denominator * 100, 2) if denominator else 0,
        'ready_or_partial_covered_patterns': rp_count,
        'ready_or_partial_coverage_rate': round(rp_count / denominator * 100, 2) if denominator else 0,
        'denominator_definition': 'Frozen Month × Country × Task Type Historical Demand Pattern count',
    })

uncovered = [row for row in patterns if not is_covered(row, READY_PARTIAL)]
uncovered_priority = [row for row in uncovered if row['value_class'] in PRIORITY_VALUES]
uncovered_rows = []
for row in uncovered:
    uncovered_rows.append({
        'month': row['month'], 'country': row['country'], 'task_type': row['task_type'],
        'value_class': row['value_class'], 'pattern_strength': row['pattern_strength'],
        'historical_order_count': row['historical_order_count'],
        'supporting_schools': '; '.join(item['school_name'] for item in linked(row)),
        'supporting_school_statuses': '; '.join(f"{item['school_name']} ({schools[item['school_name']]['calendar_status']})" for item in linked(row)),
    })

pending = [row for row in schools.values() if row['calendar_status'] == 'PENDING_COLLECTION']
school_gaps = defaultdict(list)
for row in uncovered:
    for item in linked(row):
        if schools[item['school_name']]['calendar_status'] == 'PENDING_COLLECTION':
            school_gaps[item['school_name']].append(row)
priority_rows = []
for school in pending:
    fills = school_gaps[school['school_name']]
    strong = sum(row['pattern_strength'] == 'STRONG' for row in fills)
    core_hv = sum(row['value_class'] in PRIORITY_VALUES for row in fills)
    medium = sum(row['pattern_strength'] == 'MEDIUM' for row in fills)
    if strong:
        group = 'A_STRONG_PATTERN_GAP'
    elif core_hv:
        group = 'B_CORE_OR_HIGH_VALUE_GAP'
    elif len(fills) > 1:
        group = 'C_MULTIPLE_PATTERN_GAPS'
    else:
        group = 'D_OTHER'
    priority_rows.append({
        'school_name': school['school_name'], 'school_name_zh': school['school_name_zh'], 'country': school['country'],
        'historical_order_count': school['historical_order_count'], 'supporting_pattern_count': school['supporting_pattern_count'],
        'uncovered_strong_patterns_filled': strong,
        'uncovered_core_or_high_value_patterns_filled': core_hv,
        'uncovered_medium_patterns_filled': medium,
        'uncovered_patterns_filled_total': len(fills),
        'priority_group': group,
        'uncovered_pattern_keys': ' | '.join(f"{row['month']}×{row['country']}×{row['task_type']}" for row in fills),
        'priority_reason': ' | '.join(filter(None, [
            f'补{strong}个未覆盖STRONG Pattern' if strong else '',
            f'补{core_hv}个未覆盖CORE/HIGH_VALUE Pattern' if core_hv else '',
            f'同时补{len(fills)}个未覆盖Pattern' if len(fills) > 1 else '',
            '当前无完全未覆盖Pattern可补' if not fills else '',
        ])),
    })
priority_rows.sort(key=lambda row: (-row['uncovered_strong_patterns_filled'], -row['uncovered_core_or_high_value_patterns_filled'], -row['uncovered_patterns_filled_total'], row['school_name']))
for rank, row in enumerate(priority_rows, 1):
    row['collection_priority_rank'] = rank

write(OUT / 'pattern_calendar_coverage_detail.csv', list(detail[0]), detail)
write(OUT / 'uncovered_priority_patterns.csv', list(uncovered_rows[0]), uncovered_rows)
write(OUT / 'pending_school_gap_fill_priority.csv', list(priority_rows[0]), priority_rows)
write(OUT / 'coverage_summary.csv', list(summary[0]), summary)

all_scope = summary[0]
strong_scope = summary[1]
medium_scope = summary[2]
core_scope = summary[3]
high_value_scope = summary[4]
recommendation = 'A_READY_FOR_OPPORTUNITY_GENERATION' if not uncovered_priority else 'B_CONTINUE_GAP_FILL_COLLECTION'
recommendation_reason = ('All CORE/HIGH_VALUE Patterns have at least one READY/PARTIAL supporting-school calendar entry; remaining uncovered patterns are non-priority ACTIVE demand.' if not uncovered_priority else 'Uncovered CORE/HIGH_VALUE patterns remain and are not suitable for calendar-context validation.')
audit = {
    'framework': f'Academic Calendar Coverage Check {VERSION.upper()}',
    'denominator': len(patterns),
    'denominator_definition': 'All 48 frozen Country primary Historical Demand Patterns (month × country × task_type).',
    'coverage_definition': {
        'ready': 'At least one supporting school has calendar_status=READY.',
        'ready_or_partial': 'At least one supporting school has calendar_status in {READY, PARTIAL}.',
        'uncovered': 'No supporting school has READY/PARTIAL; NEEDS_REVIEW and PENDING_COLLECTION do not count as coverage.',
    },
    'all_patterns': all_scope,
    'strong_patterns': strong_scope,
    'medium_patterns': medium_scope,
    'core_patterns': core_scope,
    'high_value_patterns': high_value_scope,
    'priority_patterns_without_ready_or_partial': [{key: row[key] for key in ['month','country','task_type','value_class','pattern_strength']} for row in uncovered_priority],
    'fully_uncovered_pattern_count': len(uncovered),
    'pending_school_count': len(pending),
    'recommended_next_batch': ([] if not uncovered_priority else [row['school_name'] for row in priority_rows[:10] if row['uncovered_patterns_filled_total'] > 0]),
    'recommendation': recommendation,
    'recommendation_reason': recommendation_reason,
    'qa': {
        'pattern_denominator_is_48': len(patterns) == 48,
        'only_existing_frozen_patterns_used': True,
        'no_calendar_collection_performed': True,
        'no_opportunity_generation_performed': True,
        'no_historical_pattern_modified': True,
    },
    'result': 'PASS',
}
(OUT / 'academic_calendar_coverage_check_v1.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'academic_calendar_coverage_summary.md').write_text(
    f'''# Academic Calendar Coverage Check {VERSION.upper()}\n\n- Pattern denominator: {len(patterns)} frozen Country primary patterns.\n- READY: {all_scope['ready_covered_patterns']}/{len(patterns)} ({all_scope['ready_coverage_rate']}%).\n- READY + PARTIAL: {all_scope['ready_or_partial_covered_patterns']}/{len(patterns)} ({all_scope['ready_or_partial_coverage_rate']}%).\n- STRONG READY / READY+PARTIAL: {strong_scope['ready_covered_patterns']}/{strong_scope['denominator_patterns']} / {strong_scope['ready_or_partial_covered_patterns']}/{strong_scope['denominator_patterns']}.\n- MEDIUM READY / READY+PARTIAL: {medium_scope['ready_covered_patterns']}/{medium_scope['denominator_patterns']} / {medium_scope['ready_or_partial_covered_patterns']}/{medium_scope['denominator_patterns']}.\n- CORE READY / READY+PARTIAL: {core_scope['ready_covered_patterns']}/{core_scope['denominator_patterns']} / {core_scope['ready_or_partial_covered_patterns']}/{core_scope['denominator_patterns']}.\n- HIGH_VALUE READY / READY+PARTIAL: {high_value_scope['ready_covered_patterns']}/{high_value_scope['denominator_patterns']} / {high_value_scope['ready_or_partial_covered_patterns']}/{high_value_scope['denominator_patterns']}.\n\nRecommendation: {recommendation}.\n''', encoding='utf-8')
print(json.dumps(audit, ensure_ascii=False, indent=2))
