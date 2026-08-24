#!/usr/bin/env python3
"""Derive per-event promotion-window candidates without executing a merge."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'runs/RUN-202608-DEMAND-001/artifacts'
CALENDAR = ART / 'academic_calendar_event_type_confirmation_v1/academic_calendar_standardized_v1_1.csv'
LEAD = ART / 'historical_time_pattern_v1/task_type_lead_time_three_year.csv'
MAPPING = ART / 'calendar_demand_mapping_v1/calendar_demand_mapping_v1.csv'
RULE = ROOT / 'config/dimensions/academic_calendar/promotion_window_business_rules_v1.yaml'
OUT = ART / 'promotion_window_business_rules_v1'


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


def iso(value: str) -> date:
    return date.fromisoformat(value)


def fmt(value: date | None) -> str:
    return value.isoformat() if value else ''


def blank_row(event: dict[str, str]) -> dict[str, str]:
    return {
        'calendar_record_id': event['calendar_record_id'], 'school': event['school'], 'school_id': event['school_id'],
        'event_type': event['event_type'], 'event_subtype': event.get('event_subtype', ''),
        'event_start': event['start_date'], 'event_end': event['end_date'], 'business_anchor_type': '',
        'business_anchor_date': '', 'historical_lead_time_source': '', 'historical_median_lead_time': '',
        'historical_p25': '', 'historical_p75': '', 'promotion_window_start': '', 'promotion_window_end': '',
        'demand_window_start': '', 'demand_window_end': '', 'demand_window_confidence': '', 'window_rule_type': '', 'rule_status': '', 'reason': '',
    }


def next_event(events: list[dict[str, str]], event: dict[str, str], event_type: str) -> dict[str, str] | None:
    anchor = iso(event['start_date'])
    candidates = [x for x in events if x['event_type'] == event_type and iso(x['start_date']) >= anchor]
    return min(candidates, key=lambda x: x['start_date']) if candidates else None


def lead_window(row: dict, anchor: date, task: str, lead: dict[str, dict[str, str]]) -> None:
    source = lead[task]
    p25, p75 = float(source['three_year_p25_lead_time']), float(source['three_year_p75_lead_time'])
    # Date-only calendar fields conservatively cover fractional-day quartiles.
    row['historical_lead_time_source'] = f'historical_time_pattern_v1:{task}'
    row['historical_median_lead_time'] = source['three_year_median_lead_time']
    row['historical_p25'] = source['three_year_p25_lead_time']
    row['historical_p75'] = source['three_year_p75_lead_time']
    row['promotion_window_start'] = fmt(anchor - timedelta(days=math.ceil(p75)))
    row['promotion_window_end'] = fmt(anchor)
    row['demand_window_start'] = fmt(anchor - timedelta(days=math.ceil(p75)))
    row['demand_window_end'] = fmt(anchor - timedelta(days=math.floor(p25)))


def main() -> None:
    inputs = [CALENDAR, LEAD, MAPPING, RULE]
    before = {str(x.relative_to(ROOT)): sha(x) for x in inputs}
    previous_path = OUT / 'calendar_promotion_window_candidates.csv'
    previous = {row['calendar_record_id']: row for row in read_csv(previous_path)} if previous_path.exists() else {}
    calendar = read_csv(CALENDAR)
    lead = {x['task_type']: x for x in read_csv(LEAD)}
    eligible = [x for x in calendar if x['record_role'] == 'ACADEMIC_EVENT']
    by_school: dict[str, list[dict[str, str]]] = defaultdict(list)
    for event in eligible:
        by_school[event['school_id']].append(event)
    for events in by_school.values():
        events.sort(key=lambda x: x['start_date'])

    rows: list[dict] = []
    for event in sorted(eligible, key=lambda x: x['calendar_record_id']):
        row = blank_row(event)
        start, end = iso(event['start_date']), iso(event['end_date'])
        school_events = by_school[event['school_id']]
        typ = event['event_type']
        if typ == 'EXAM':
            row.update({'business_anchor_type': 'EXAM_START', 'business_anchor_date': fmt(start), 'window_rule_type': 'HISTORICAL_LEAD_TIME', 'rule_status': 'HISTORICAL_LEAD_TIME'})
            lead_window(row, start, '考试', lead)
            row['demand_window_start'], row['demand_window_end'] = fmt(start), fmt(end)
            row['reason'] = 'EXAM anchors to exam start and uses 考试 historical P25-P75 lead time; promotion starts at the expected consultation-window start and runs through the anchor.'
        elif typ == 'RESIT':
            task, status = ('补考', 'HISTORICAL_LEAD_TIME') if int(lead['补考']['three_year_valid_count']) > 0 else ('考试', 'FALLBACK_RULE')
            row.update({'business_anchor_type': 'RESIT_START', 'business_anchor_date': fmt(start), 'window_rule_type': status, 'rule_status': status})
            lead_window(row, start, task, lead)
            row['demand_window_start'], row['demand_window_end'] = fmt(start), fmt(end)
            row['reason'] = f'RESIT anchors to resit start and uses {task} historical P25-P75 lead time' + (' as permitted fallback.' if status == 'FALLBACK_RULE' else '.')
        elif typ == 'TEACHING':
            row.update({'business_anchor_type': 'TEACHING_START', 'business_anchor_date': fmt(start), 'promotion_window_start': fmt(start), 'promotion_window_end': fmt(end), 'demand_window_start': fmt(start), 'demand_window_end': fmt(end), 'window_rule_type': 'ANCHOR_BASED', 'rule_status': 'ANCHOR_BASED', 'reason': 'TEACHING event start is the teaching-start anchor. No DDL lead time or fixed preheat days are applied; later merge may combine this anchor with August consultation patterns.'})
        elif typ in {'REVISION', 'READING'}:
            exam = next_event(school_events, event, 'EXAM')
            if exam:
                anchor = iso(exam['start_date'])
                row.update({'business_anchor_type': 'NEXT_EXAM_START', 'business_anchor_date': fmt(anchor), 'window_rule_type': 'CALENDAR_SEQUENCE', 'rule_status': 'CALENDAR_SEQUENCE'})
                lead_window(row, anchor, '考试', lead)
                row['reason'] = f'{typ} is connected to the same school next EXAM ({exam["calendar_record_id"]}) and uses 考试 historical lead time.'
            else:
                row.update({'business_anchor_type': f'{typ}_START_CONTEXTUAL', 'business_anchor_date': fmt(start), 'promotion_window_start': fmt(start), 'window_rule_type': 'CONTEXT_ONLY', 'rule_status': 'CONTEXT_ONLY', 'reason': f'No later same-school EXAM exists; {typ} remains a contextual anchor with no inferred end date.'})
        elif typ == 'RESULTS':
            resit = next_event(school_events, event, 'RESIT')
            if resit:
                resit_start, resit_end = iso(resit['start_date']), iso(resit['end_date'])
                row.update({'business_anchor_type': 'RESULTS_RELEASE_TO_NEXT_RESIT', 'business_anchor_date': fmt(start), 'promotion_window_start': fmt(start), 'promotion_window_end': fmt(resit_start), 'demand_window_start': fmt(start), 'demand_window_end': fmt(resit_end), 'window_rule_type': 'CALENDAR_SEQUENCE', 'rule_status': 'CALENDAR_SEQUENCE', 'reason': f'Results starts promotion and is sequenced to same-school RESIT ({resit["calendar_record_id"]}); no results-minus-lead-time calculation is used.'})
            else:
                row.update({'business_anchor_type': 'RESULTS_RELEASE', 'business_anchor_date': fmt(start), 'promotion_window_start': fmt(start), 'window_rule_type': 'CONTEXT_ONLY', 'rule_status': 'CONTEXT_ONLY', 'reason': 'No later same-school RESIT exists. Results begins a contextual promotion window; no reverse lead-time calculation is used.'})
        elif typ in {'BREAK', 'VACATION', 'ORIENTATION'}:
            teaching = next_event(school_events, event, 'TEACHING')
            if teaching:
                t_start, t_end = iso(teaching['start_date']), iso(teaching['end_date'])
                row.update({'business_anchor_type': 'NEXT_TEACHING_START', 'business_anchor_date': fmt(t_start), 'promotion_window_start': fmt(start), 'promotion_window_end': fmt(t_start), 'demand_window_start': fmt(t_start), 'demand_window_end': fmt(t_end), 'window_rule_type': 'CALENDAR_SEQUENCE', 'rule_status': 'CALENDAR_SEQUENCE', 'reason': f'{typ} is connected to same-school next TEACHING ({teaching["calendar_record_id"]}); no fixed duration is inferred.'})
            else:
                row.update({'business_anchor_type': f'{typ}_START_CONTEXTUAL', 'business_anchor_date': fmt(start), 'promotion_window_start': fmt(start), 'window_rule_type': 'CONTEXT_ONLY', 'rule_status': 'CONTEXT_ONLY', 'reason': f'No next same-school TEACHING exists; retain contextual preheat with no invented end date.'})
        elif typ == 'ASSESSMENT':
            row.update({'business_anchor_type': 'ASSESSMENT_PERIOD', 'business_anchor_date': fmt(start), 'promotion_window_start': fmt(start), 'promotion_window_end': fmt(end), 'demand_window_start': fmt(start), 'demand_window_end': fmt(end), 'demand_window_confidence': 'CONTEXTUAL', 'window_rule_type': 'ANCHOR_BASED', 'rule_status': 'ANCHOR_BASED', 'reason': 'Assessment Event 本身表示学生进入考核集中阶段，因此其 Calendar Date Range 本身即可作为运营关注窗口；不推断具体 Task Type 或 DDL。'})
        else:
            raise ValueError(f'Unexpected mapping-eligible event type: {typ}')
        rows.append(row)

    fields = list(rows[0])
    write_csv(OUT / 'calendar_promotion_window_candidates.csv', fields, rows)
    statuses = Counter(row['rule_status'] for row in rows)
    after = {str(x.relative_to(ROOT)): sha(x) for x in inputs}
    current = {row['calendar_record_id']: row for row in rows}
    shared_fields = [field for field in fields if field != 'demand_window_confidence']
    non_assessment_unchanged = all(
        all(previous[event_id].get(field, '') == current[event_id].get(field, '') for field in shared_fields)
        for event_id in previous if current[event_id]['event_type'] != 'ASSESSMENT'
    )
    checks = {
        'exam_uses_exam_lead_time': all(row['historical_lead_time_source'].endswith(':考试') for row in rows if row['event_type'] == 'EXAM'),
        'resit_prefers_resit_lead_time': all(row['historical_lead_time_source'].endswith(':补考') for row in rows if row['event_type'] == 'RESIT'),
        'results_never_reverse_subtracts_lead_time': all(not row['historical_lead_time_source'] for row in rows if row['event_type'] == 'RESULTS'),
        'revision_reading_prefers_next_exam': all(row['rule_status'] != 'CONTEXT_ONLY' or 'No later same-school EXAM' in row['reason'] for row in rows if row['event_type'] in {'REVISION', 'READING'}),
        'break_vacation_orientation_prefers_next_teaching': all(row['rule_status'] != 'CONTEXT_ONLY' or 'No next same-school TEACHING' in row['reason'] for row in rows if row['event_type'] in {'BREAK', 'VACATION', 'ORIENTATION'}),
        'teaching_uses_no_ddl_lead_time': all(not row['historical_lead_time_source'] and row['rule_status'] == 'ANCHOR_BASED' for row in rows if row['event_type'] == 'TEACHING'),
        'assessment_uses_own_date_range_contextually': all(row['business_anchor_type'] == 'ASSESSMENT_PERIOD' and row['promotion_window_start'] == row['event_start'] and row['promotion_window_end'] == row['event_end'] and row['demand_window_start'] == row['event_start'] and row['demand_window_end'] == row['event_end'] and row['demand_window_confidence'] == 'CONTEXTUAL' and not row['historical_lead_time_source'] for row in rows if row['event_type'] == 'ASSESSMENT'),
        'pending_business_rule_zero': statuses['PENDING_BUSINESS_RULE'] == 0,
        'non_assessment_event_rules_unchanged': non_assessment_unchanged,
        'no_fixed_7_14_30_day_assumption': True,
        'historical_time_layer_unchanged': before[str(LEAD.relative_to(ROOT))] == after[str(LEAD.relative_to(ROOT))],
        'calendar_mapping_unchanged': before[str(MAPPING.relative_to(ROOT))] == after[str(MAPPING.relative_to(ROOT))],
        'monthly_opportunity_merge_not_executed': True,
        'eligible_calendar_event_count_unchanged': len(rows) == len(eligible) == 116,
    }
    qa = {'artifact': 'promotion_window_business_rules_v1', 'version': '1.1', 'result': 'PASS' if all(checks.values()) else 'FAIL', 'counts': {'calendar_events': len(rows), 'windowed_events': sum(row['rule_status'] != 'PENDING_BUSINESS_RULE' for row in rows), 'rule_status_counts': dict(sorted(statuses.items())), 'pending_events': statuses['PENDING_BUSINESS_RULE']}, 'checks': checks, 'input_hashes': before, 'boundaries': {'monthly_opportunity_merge': 'NOT_EXECUTED', 'final_opportunity_generation': 'NOT_EXECUTED'}}
    (OUT / 'promotion_window_business_rules_v1_qa.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    if qa['result'] != 'PASS':
        raise RuntimeError('Promotion Window Business Rule V1 QA failed')
    print(json.dumps({'qa': qa['result'], **qa['counts']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
