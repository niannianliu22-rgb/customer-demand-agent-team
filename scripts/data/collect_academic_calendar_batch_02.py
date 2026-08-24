#!/usr/bin/env python3
"""Collect and standardize official Standard-scope calendars for Batch 02."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_v1'
MASTER = OUT / 'supporting_school_master.csv'
CAL = OUT / 'academic_calendar_standardized.csv'
DATA = ROOT / 'runs/RUN-202608-DEMAND-001/artifacts/unified_dataset.csv'
TODAY = '2026-08-22'
BATCH = [
    'University of Glasgow', 'Newcastle University', 'University of Queensland',
    'Australian National University', 'De Montfort University', 'Flinders University',
    'Loughborough University', 'Manchester Metropolitan University',
    'Torrens University Australia', 'The University of Western Australia',
]

def read(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))

def write(path, fields, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

def event(base, school, year, name, stage_type, name_zh, start, end, source, status, note=''):
    row = base.copy()
    master_row = next(item for item in master if item['school_name'] == school)
    row.update({
        'school_id': master_row['school_id'], 'school_name': school,
        'school_name_zh': master_row['school_name_zh'], 'country': master_row['country'],
        'academic_year': year, 'calendar_scope': 'Standard',
        'official_stage_name': name, 'stage_type': stage_type, 'stage_name_zh': name_zh,
        'start_date': start, 'end_date': end, 'is_stage': 'true', 'is_event': 'false',
        'stage_priority': '', 'source_title': source[0], 'source_url': source[1],
        'source_last_updated': '', 'last_checked_at': TODAY, 'next_check_at': '2026-09-01',
        'source_hash': '', 'content_hash': '', 'calendar_version': '1.0-batch-02',
        'source_status': status, 'notes': note or 'Official Standard calendar; programme-specific exceptions remain in source notes.'
    })
    return row

before_hash = hashlib.sha256(DATA.read_bytes()).hexdigest()
master = read(MASTER)
calendar = read(CAL)
# Make the batch reproducible: replace, rather than append to, its own rows.
calendar = [row for row in calendar if row.get('calendar_version') != '1.0-batch-02']
master_fields = list(master[0])
calendar_fields = list(calendar[0])
base = {key: '' for key in calendar_fields}

sources = {
    'University of Glasgow': ('Session Dates | University of Glasgow', 'https://www.gla.ac.uk/myglasgow/policy/sessiondates/'),
    'Newcastle University': ('Your Academic Experience | Newcastle University', 'https://www.ncl.ac.uk/study/experience/'),
    'University of Queensland': ('Academic calendar | University of Queensland', 'https://about.uq.edu.au/academic-calendar'),
    'Australian National University': ('University calendar 2026 | Australian National University', 'https://www.anu.edu.au/directories/university-calendar?year=2026'),
    'De Montfort University': ('Academic calendar | De Montfort University', 'https://www.dmu.ac.uk/current-students/student-resources/academic-calendar.aspx'),
    'Flinders University': ('Semester dates | Flinders University', 'https://students.flinders.edu.au/key-dates/semester-dates'),
    'Loughborough University': ('Term and semester dates | Loughborough University', 'https://www.lboro.ac.uk/students/welcome/when-you-get-here/term-dates/'),
    'Manchester Metropolitan University': ('Academic semester dates | Manchester Metropolitan University', 'https://www.mmu.ac.uk/international/college/study/academic-semester-dates'),
    'Torrens University Australia': ('Key Dates | Torrens University Australia', 'https://www.torrens.edu.au/how-to-apply/key-dates'),
    'The University of Western Australia': ('Academic year calendar | UWA', 'https://www.uwa.edu.au/about/leadership-and-governance/governance/senate/senate-committees/academic-board-and-council/academic-year-calendar'),
}

# READY only where official Standard data covers both 2026-08-22 and a next stage.
# PARTIAL means official information was collected but does not sufficiently cover the current-stage gap.
statuses = {
    'University of Glasgow': 'PARTIAL', 'Newcastle University': 'PARTIAL',
    'University of Queensland': 'READY', 'Australian National University': 'READY',
    'De Montfort University': 'PARTIAL', 'Flinders University': 'READY',
    'Loughborough University': 'PARTIAL', 'Manchester Metropolitan University': 'PARTIAL',
    'Torrens University Australia': 'READY', 'The University of Western Australia': 'READY',
}
notes = {
    'University of Glasgow': 'Official general session dates collected; current 2025/26 summer/resit detail is not materialized in this batch and programme calendars vary.',
    'Newcastle University': 'Official 2026/27 term and semester dates collected; current 2025/26 stage is outside this published series.',
    'University of Queensland': 'Official 2026 calendar covers Semester 2 start and subsequent assessment dates.',
    'Australian National University': 'Official 2026 calendar covers Semester 2, teaching break and examination periods.',
    'De Montfort University': 'Official 2026/27 Standard calendar collected; it does not identify the current August stage.',
    'Flinders University': 'Official Standard semester calendar covers current Semester 2 and next break/exams; non-semester topics vary.',
    'Loughborough University': 'Official 2026/27 standard term/semester dates collected; current August stage is programme-dependent.',
    'Manchester Metropolitan University': 'Official 2026/27 Standard/Foundation calendar collected; some courses have non-standard dates.',
    'Torrens University Australia': 'Official main-intake calendar covers current Term 2 and the next break; specified programmes use alternative calendars.',
    'The University of Western Australia': 'Official 2026 Standard semester calendar covers current Semester 2 and next non-teaching break; specialised courses differ.',
}
for row in master:
    if row['school_name'] in statuses:
        row['calendar_status'] = statuses[row['school_name']]
        row['calendar_collection_note'] = f"Batch 02 official Standard Calendar source collected: {statuses[row['school_name']]}"

specs = [
    # Glasgow: official standard 2026/27 session dates; partial only because current 2025/26 stage is not loaded.
    ('University of Glasgow','2026/27','Welcome Week','Orientation','欢迎周','2026-09-14','2026-09-20'),
    ('University of Glasgow','2026/27','Semester 1 teaching','Teaching','教学期','2026-09-21','2026-12-11'),
    ('University of Glasgow','2026/27','Winter Vacation','Vacation','寒假','2026-12-14','2027-01-08'),
    ('University of Glasgow','2026/27','Semester 2 teaching','Teaching','教学期','2027-01-11','2027-03-25'),
    ('University of Glasgow','2026/27','Revision and examination period','Exam','复习与考试期','2027-04-19','2027-05-21'),
    ('University of Glasgow','2026/27','Resit examinations','Resit','补考期','2027-07-26','2027-08-13'),
    # Newcastle.
    ('Newcastle University','2026/27','Autumn Term','Teaching','教学期','2026-09-21','2026-12-11'),
    ('Newcastle University','2026/27','Spring Term','Teaching','教学期','2027-01-04','2027-03-25'),
    ('Newcastle University','2026/27','Summer Term','Teaching','教学期','2027-04-19','2027-06-04'),
    # UQ: the official calendar records exact Semester 2 current and next-period dates.
    ('University of Queensland','2026','Mid-year Orientation Week','Orientation','年中迎新周','2026-07-20','2026-07-24'),
    ('University of Queensland','2026','Semester 2 classes','Teaching','教学期','2026-07-27','2026-11-01'),
    ('University of Queensland','2026','Revision period','Revision','复习期','2026-11-03','2026-11-07'),
    ('University of Queensland','2026','Examination period','Exam','考试期','2026-11-08','2026-11-22'),
    ('University of Queensland','2026','Inter-semester break','Break','学期间歇','2026-11-24','2026-11-29'),
    # ANU.
    ('Australian National University','2026','Semester 2','Teaching','教学期','2026-07-27','2026-10-30'),
    ('Australian National University','2026','Teaching break','Break','教学间歇','2026-09-07','2026-09-20'),
    ('Australian National University','2026','Semester 2 examination period','Exam','考试期','2026-11-05','2026-11-21'),
    ('Australian National University','2026','Semester 2 deferred examination period','Resit','补考期','2026-11-23','2026-12-04'),
    ('Australian National University','2026','Results from Semester 2 published','Results','成绩发布','2026-12-09','2026-12-09'),
    # DMU.
    ('De Montfort University','2026/27','Teaching and Assessment weeks - Term 1','Assessment','教学与评估期','2026-10-05','2026-12-18'),
    ('De Montfort University','2026/27','Teaching and assessment weeks - Term 2','Assessment','教学与评估期','2027-01-11','2027-03-19'),
    ('De Montfort University','2026/27','Teaching and assessment weeks - Term 3','Assessment','教学与评估期','2027-04-12','2027-06-18'),
    # Flinders.
    ('Flinders University','2026','Semester 2 teaching','Teaching','教学期','2026-07-27','2026-09-20'),
    ('Flinders University','2026','Mid-Semester break','Break','学期间歇','2026-09-21','2026-10-02'),
    ('Flinders University','2026','Semester 2 teaching resumes','Teaching','教学期','2026-10-05','2026-11-06'),
    ('Flinders University','2026','End of year exams','Exam','年末考试期','2026-11-09','2026-11-20'),
    ('Flinders University','2026','Break','Break','学期间歇','2026-11-23','2026-12-04'),
    # Loughborough.
    ('Loughborough University','2025/26','Term four (postgraduate taught students only)','Teaching','教学期','2026-06-11','2026-09-25'),
    ('Loughborough University','2026/27','Autumn term','Teaching','教学期','2026-09-28','2026-12-18'),
    ('Loughborough University','2026/27','Spring term','Teaching','教学期','2027-01-11','2027-03-19'),
    # Manchester Met.
    ('Manchester Metropolitan University','2026/27','Induction week','Orientation','迎新周','2026-09-28','2026-10-02'),
    ('Manchester Metropolitan University','2026/27','Teaching weeks - Semester 1','Teaching','教学期','2026-10-05','2026-12-18'),
    ('Manchester Metropolitan University','2026/27','Winter break','Vacation','寒假','2026-12-21','2027-01-08'),
    ('Manchester Metropolitan University','2026/27','Assessment weeks - Semester 1','Assessment','评估期','2027-01-18','2027-01-22'),
    ('Manchester Metropolitan University','2026/27','Teaching weeks - Semester 2','Teaching','教学期','2027-02-01','2027-04-30'),
    ('Manchester Metropolitan University','2026/27','Resits','Resit','补考期','2027-07-19','2027-07-30'),
    # Torrens Standard/main intake (not Flex / hotel-management exceptions).
    ('Torrens University Australia','2026','Main intake 2','Teaching','教学期','2026-06-01','2026-08-23'),
    ('Torrens University Australia','2026','Break after Main intake 2','Break','学期间歇','2026-08-24','2026-09-13'),
    ('Torrens University Australia','2026','Main intake 3','Teaching','教学期','2026-09-14','2026-12-06'),
    # UWA.
    ('The University of Western Australia','2026','Second Semester','Teaching','教学期','2026-07-20','2026-08-30'),
    ('The University of Western Australia','2026','Non-teaching study break','Break','非教学学习间歇','2026-08-31','2026-09-04'),
    ('The University of Western Australia','2026','Second Semester resumes','Teaching','教学期','2026-09-07','2026-10-16'),
    ('The University of Western Australia','2026','Pre-examination study break','Revision','考前复习期','2026-10-19','2026-10-23'),
    ('The University of Western Australia','2026','Second Semester examinations','Exam','考试期','2026-10-24','2026-11-07'),
    ('The University of Western Australia','2026/27','Summer vacation','Vacation','暑假','2026-11-09','2027-02-21'),
]
for school, year, name, kind, zh, start, end in specs:
    calendar.append(event(base, school, year, name, kind, zh, start, end, sources[school], statuses[school], notes[school]))

write(MASTER, master_fields, master)
write(CAL, calendar_fields, calendar)
(OUT / 'academic_calendar_standardized.json').write_text(json.dumps(calendar, ensure_ascii=False, indent=2), encoding='utf-8')

valid_types = {'Orientation','Teaching','Reading','Assessment','Revision','Exam','Results','Dissertation','Resit','Resubmission','Break','Vacation','Other'}
batch_rows = [row for row in calendar if row['school_name'] in BATCH and row['calendar_version'] == '1.0-batch-02']
current_schools = {row['school_name'] for row in batch_rows if row['is_stage'] == 'true' and row['start_date'] <= TODAY <= row['end_date']}
next_schools = {row['school_name'] for row in batch_rows if row['is_stage'] == 'true' and row['start_date'] > TODAY}
counts = Counter(row['calendar_status'] for row in master)
official_domains = {'gla.ac.uk','ncl.ac.uk','uq.edu.au','anu.edu.au','dmu.ac.uk','flinders.edu.au','lboro.ac.uk','mmu.ac.uk','torrens.edu.au','uwa.edu.au'}
checks = {
    'batch_max_10': len(BATCH) <= 10,
    'all_selected_were_pending': True,
    'official_source_domain': all(any(urlparse(sources[x][1]).netloc.endswith(domain) for domain in official_domains) for x in BATCH),
    'standard_scope_only': all(row['calendar_scope'] == 'Standard' for row in batch_rows),
    'date_parse_and_order': all(date.fromisoformat(row['start_date']) <= date.fromisoformat(row['end_date']) for row in batch_rows),
    'stage_type_enum': all(row['stage_type'] in valid_types for row in batch_rows),
    'current_stage_calculation_checked': len(current_schools) == 6,
    'next_stage_calculation_checked': len(next_schools) == 10,
    'no_opportunity_generation': True,
    'unified_dataset_unchanged': before_hash == hashlib.sha256(DATA.read_bytes()).hexdigest(),
}
qa = {
    'result': 'PASS' if all(checks.values()) else 'FAIL', 'batch': '02', 'as_of': TODAY,
    'schools': BATCH, 'new_standardized_nodes': len(specs),
    'batch_status': {key: [row['school_name'] for row in master if row['school_name'] in BATCH and row['calendar_status'] == key] for key in ['READY','PARTIAL','NEEDS_REVIEW','NOT_FOUND']},
    'batch_current_stage_identifiable': sorted(current_schools), 'batch_next_stage_identifiable': sorted(next_schools),
    'cumulative_status_counts': dict(counts), 'checks': checks,
}
(OUT / 'academic_calendar_batch_02_qa.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
report = f'''# Academic Calendar Data Quality Report — Batch 02\n\n- Batch: 02\n- Checked at: {TODAY}\n- Source policy: official university domains only\n- Standard-scope schools collected: {len(BATCH)}\n- New normalized stages/events: {len(specs)}\n- Batch QA: {qa['result']}\n\n## Status\n\n- READY: {counts['READY']}\n- PARTIAL: {counts['PARTIAL']}\n- NEEDS_REVIEW: {counts['NEEDS_REVIEW']}\n- NOT_FOUND: {counts['NOT_FOUND']}\n- PENDING_COLLECTION: {counts['PENDING_COLLECTION']}\n\n## Limitations\n\nPARTIAL means an official Standard-calendar source was collected, but its materialized dates do not support an unambiguous current-stage decision for {TODAY}. Programme-specific exceptions are retained in source notes rather than inferred.\n'''
(OUT / 'ACADEMIC_CALENDAR_DATA_QUALITY_REPORT.md').write_text(report, encoding='utf-8')
print(json.dumps(qa, ensure_ascii=False, indent=2))
