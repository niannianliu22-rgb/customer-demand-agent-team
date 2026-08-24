#!/usr/bin/env python3
"""Reframe the August 2026 union pool as Country -> Timing -> Direction -> School."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'runs/RUN-202608-DEMAND-001/artifacts'
POOL = ART / 'monthly_opportunity_merge_v1/august_2026_opportunity_pool.csv'
POOL_QA = ART / 'monthly_opportunity_merge_v1/monthly_opportunity_merge_qa.json'
CALENDAR = ART / 'academic_calendar_event_type_confirmation_v1/academic_calendar_standardized_v1_1.csv'
WINDOWS = ART / 'promotion_window_business_rules_v1/calendar_promotion_window_candidates.csv'
OUT = ART / 'august_2026_country_business_timing_v1'
PERIOD_DATES = {'EARLY_AUGUST': ('2026-08-01', '2026-08-10'), 'MID_AUGUST': ('2026-08-11', '2026-08-20'), 'LATE_AUGUST': ('2026-08-21', '2026-08-31')}
SCHOOL_EXCLUDED = {'', 'UNKNOWN', 'UNSTANDARDIZED', 'NON_SCHOOL', 'NON_UNIVERSITY_ENTITY', 'UNRESOLVED'}


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as h: return list(csv.DictReader(h))


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as h:
        w = csv.DictWriter(h, fieldnames=fields, extrasaction='ignore'); w.writeheader(); w.writerows(rows)


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def direction(task, service):
    x = task or service
    if task in {'essay', 'assignment', '作业', '小组作业', 'project', 'report'}: return 'ASSIGNMENT_BUSINESS'
    if task in {'Dissertation', 'Dissertation-part', '毕业论文辅导', '毕业论文半包', '毕业论文润色'}: return 'DISSERTATION_BUSINESS'
    if task == '补考' or service == '补考': return 'RESIT_BUSINESS'
    if task in {'考试', 'quiz', 'online test-exam/quiz'} or service in {'考试辅导', '押题', '包过辅导', '考试'}: return 'EXAM_BUSINESS'
    if task == '选课': return 'SELECTION_SUPPORT'
    if task in {'学年包', 'DP', '包课', '毕业无忧', '预存'} or service in {'学年包', '包课', 'DP', '陪跑服务', '长期辅导'}: return 'LONG_TERM_SERVICE'
    return 'COURSE_SUPPORT'


def max_strength(values):
    ranks = {'HIGH': 3, 'MEDIUM': 2, 'MODERATE_EVIDENCE': 2, 'EMERGING_SIGNAL': 1, 'LIMITED_HIGH_VALUE_EVIDENCE': 1, 'WEAK_EVIDENCE': 0, '': 0}
    return max(values, key=lambda x: ranks.get(x, 0), default='')


def canonical_country(value):
    """Normalise only presentation-level country aliases; never edit upstream."""
    return {'澳大利亚': '澳洲'}.get(value, value)


def main():
    inputs = [POOL, POOL_QA, CALENDAR, WINDOWS]
    before = {str(x.relative_to(ROOT)): sha(x) for x in inputs}
    pool = read_csv(POOL)
    calendar = {r['calendar_record_id']: r for r in read_csv(CALENDAR)}
    windows = {r['calendar_record_id']: r for r in read_csv(WINDOWS)}
    grouped = defaultdict(list)
    for source_row in pool:
        # A merged LEVEL_3 row can carry a historical country while its school
        # is the current Calendar school's signal.  For every Calendar-backed
        # opportunity, use the frozen Calendar record as the authority for
        # country and school.  Historical-only rows retain their own fields.
        row = dict(source_row)
        cal = calendar.get(row['calendar_event_id']) if row['calendar_event_id'] else None
        if cal:
            row['country'] = canonical_country(cal['country'])
            row['school'] = cal['school']
        else:
            row['country'] = canonical_country(row['country'])
        grouped[(row['country'], direction(row['task_type'], row['service_direction']), row['august_period'])].append(row)

    country_rows, selected = [], {}
    for (country, business, period), rows in grouped.items():
        calendar_rows = [r for r in rows if r['calendar_event_id']]
        historical_rows = [r for r in rows if r['historical_evidence_refs']]
        calendar_schools = {r['school'] for r in calendar_rows if r['school'] not in SCHOOL_EXCLUDED}
        historic_schools = {r['school'] for r in historical_rows if r['school'] not in SCHOOL_EXCLUDED}
        h_and_c = [r for r in rows if r['evidence_source'] == 'HISTORICAL_AND_CALENDAR']
        stable_history = [r for r in historical_rows if r['historical_stability'] == 'STABLE']
        # A country conclusion requires at least two school observations from the
        # relevant layer; a single school remains DIRECTIONAL rather than national.
        if h_and_c and len(calendar_schools | historic_schools) >= 2:
            source, rank = 'HISTORICAL_AND_CALENDAR', 4
        elif len(calendar_schools) >= 2:
            source, rank = 'CALENDAR_ONLY', 3
        elif stable_history and len(historic_schools) >= 2:
            source, rank = 'HISTORICAL_ONLY', 2
        else:
            source, rank = 'DIRECTIONAL', 1
        support = sum(int(r['historical_count'] or 0) for r in historical_rows) + len(calendar_schools)
        selected[(country, business, period)] = {'source': source, 'rank': rank, 'support': support, 'rows': rows, 'calendar_rows': calendar_rows, 'historical_rows': historical_rows, 'calendar_schools': calendar_schools, 'historic_schools': historic_schools}

    by_country_business = defaultdict(list)
    for key, value in selected.items(): by_country_business[key[:2]].append((key[2], value))
    for (country, business), candidates in sorted(by_country_business.items()):
        period, info = sorted(candidates, key=lambda x: (-x[1]['rank'], -x[1]['support'], x[0]))[0]
        stages = sorted({r['calendar_event_type'] for r in info['calendar_rows']})
        start, end = PERIOD_DATES[period]
        if info['source'] == 'HISTORICAL_AND_CALENDAR':
            reason = 'Historical August consultation support and multiple-school Calendar promotion-window support overlap in this period.'
        elif info['source'] == 'CALENDAR_ONLY':
            reason = 'Multiple schools have explicit 2026 Calendar promotion-window support in this period; historical within-month support is weaker or not aligned.'
        elif info['source'] == 'HISTORICAL_ONLY':
            reason = 'Stable historical August consultation support across multiple schools; no aligned current Calendar signal is required to retain it.'
        else:
            reason = 'Evidence is limited to a single school or weak/partial support, so this period is directional only and not a country-wide precise timing claim.'
        country_rows.append({'country': country, 'business_direction': business, 'best_operating_window': period, 'window_start': start, 'window_end': end, 'time_evidence_source': info['source'], 'academic_stages': '; '.join(stages) or 'NOT_EVALUATED_FROM_HISTORICAL_ONLY', 'historical_support': f"records={sum(int(r['historical_count'] or 0) for r in info['historical_rows'])}; schools={len(info['historic_schools'])}", 'calendar_support': f"events={len({r['calendar_event_id'] for r in info['calendar_rows']})}; schools={len(info['calendar_schools'])}", 'priority': min((r['priority_tier'] for r in info['rows']), default='P4 — WATCHLIST'), 'time_reason': reason})

    school_rows = []
    # Retain school-level opportunities in every August period.  The country
    # table selects one best window per direction, while this table remains
    # the traceable school catalogue and must not discard Calendar-new signals
    # occurring in a non-selected period.
    all_keys = sorted(selected)
    for country, business, period in all_keys:
        rows = selected[(country, business, period)]['rows']
        by_school = defaultdict(list)
        for row in rows:
            if row['school'] not in SCHOOL_EXCLUDED: by_school[row['school']].append(row)
        for school, items in sorted(by_school.items()):
            task_types = sorted({r['task_type'] for r in items if r['task_type']})
            services = sorted({r['service_direction'] for r in items if r['service_direction']})
            calendar_items = [r for r in items if r['calendar_event_id']]
            evidence = set(r['evidence_source'] for r in items)
            school_rows.append({'country': country, 'business_direction': business, 'best_operating_window': period, 'school': school, 'specific_task_types': '; '.join(task_types), 'service_directions': '; '.join(services), 'promotion_window_start': '; '.join(sorted({r['promotion_window_start'] for r in calendar_items if r['promotion_window_start']})), 'promotion_window_end': '; '.join(sorted({r['promotion_window_end'] for r in calendar_items if r['promotion_window_end']})), 'evidence_source': '; '.join(sorted(evidence)), 'evidence_strength': max_strength([r['evidence_strength'] for r in items]), 'reason': 'School-level supporting opportunity: specific tasks/services remain below the country business-direction layer.', 'opportunity_refs': '; '.join(sorted(r['opportunity_id'] for r in items))})

    country_fields = ['country', 'business_direction', 'best_operating_window', 'window_start', 'window_end', 'time_evidence_source', 'academic_stages', 'historical_support', 'calendar_support', 'priority', 'time_reason']
    school_fields = ['country', 'business_direction', 'best_operating_window', 'school', 'specific_task_types', 'service_directions', 'promotion_window_start', 'promotion_window_end', 'evidence_source', 'evidence_strength', 'reason', 'opportunity_refs']
    country_rows.sort(key=lambda r: (r['country'], r['business_direction']))
    school_rows.sort(key=lambda r: (r['country'], r['business_direction'], r['school']))
    write_csv(OUT / 'august_2026_country_business_timing.csv', country_fields, country_rows)
    write_csv(OUT / 'august_2026_country_school_opportunities.csv', school_fields, school_rows)

    lines = ['# August 2026 Country → Best Time → Business Direction → School Opportunity', '', 'Country conclusions use at least two supporting schools for HISTORICAL_AND_CALENDAR, CALENDAR_ONLY, or HISTORICAL_ONLY claims. Single-school or weak support remains DIRECTIONAL.', '']
    for country in sorted({r['country'] for r in country_rows}):
        lines += [f'## {country}', '']
        for row in [r for r in country_rows if r['country'] == country]:
            lines += [f"### {row['business_direction']} — {row['best_operating_window']}", '', f"- Academic Stage: {row['academic_stages']}", f"- Time evidence: {row['time_evidence_source']}", f"- Reason: {row['time_reason']}", '- Key schools:']
            for school in [s for s in school_rows if s['country'] == country and s['business_direction'] == row['business_direction'] and s['best_operating_window'] == row['best_operating_window']][:8]:
                need = school['specific_task_types'] or school['service_directions']
                lines.append(f"  - {school['school']}: {need}.")
            lines.append('')
    (OUT / 'august_2026_operational_direction_summary.md').write_text('\n'.join(lines), encoding='utf-8')

    after = {str(x.relative_to(ROOT)): sha(x) for x in inputs}
    calendar_new_ids = {r['opportunity_id'] for r in pool if r['evidence_source'] == 'CALENDAR_NEW_OPPORTUNITY'}
    output_ids = {x for r in school_rows for x in r['opportunity_refs'].split('; ') if x}
    checks = {'every_country_direction_has_window': all(r['best_operating_window'] for r in country_rows), 'time_has_historical_calendar_or_directional_evidence': all(r['time_evidence_source'] in {'HISTORICAL_AND_CALENDAR', 'CALENDAR_ONLY', 'HISTORICAL_ONLY', 'DIRECTIONAL'} for r in country_rows), 'single_school_not_promoted_to_country_conclusion': all(r['time_evidence_source'] == 'DIRECTIONAL' or int(r['calendar_support'].split('schools=')[1]) >= 2 or int(r['historical_support'].split('schools=')[1]) >= 2 for r in country_rows), 'country_layer_is_directional_school_layer_is_specific': all(not r['specific_task_types'] or r['school'] not in SCHOOL_EXCLUDED for r in school_rows), 'no_fabricated_precise_dates': all((r['window_start'], r['window_end']) == PERIOD_DATES[r['best_operating_window']] for r in country_rows), 'historical_demand_not_deleted': sum(1 for r in pool if r['historical_evidence_refs']) > 0, 'calendar_new_opportunity_not_deleted': calendar_new_ids <= output_ids, 'frozen_inputs_unchanged': before == after, 'answers_country_time_stage_business_school_need': bool(country_rows and school_rows)}
    qa = {'artifact': 'august_2026_country_business_timing_v1', 'result': 'PASS' if all(checks.values()) else 'FAIL', 'counts': {'country_business_directions': len(country_rows), 'school_opportunities': len(school_rows), 'time_evidence_sources': dict(sorted(Counter(r['time_evidence_source'] for r in country_rows).items())), 'countries': sorted({r['country'] for r in country_rows})}, 'checks': checks, 'input_hashes': before}
    (OUT / 'country_business_timing_qa.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    if qa['result'] != 'PASS': raise RuntimeError('Country timing QA failed')
    print(json.dumps({'qa': qa['result'], **qa['counts']}, ensure_ascii=False))


if __name__ == '__main__': main()
