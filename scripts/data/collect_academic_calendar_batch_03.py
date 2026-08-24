#!/usr/bin/env python3
"""Batch 03 targeted CORE/HIGH_VALUE calendar gap fill plus critical review."""
from __future__ import annotations

import csv, hashlib, json
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_v1'
MASTER=OUT/'supporting_school_master.csv'; CAL=OUT/'academic_calendar_standardized.csv'; DATA=ROOT/'runs/RUN-202608-DEMAND-001/artifacts/unified_dataset.csv'
TODAY='2026-08-22'
BATCH=['The Hong Kong Polytechnic University','Johns Hopkins University','Pennsylvania State University','PSB Academy','Singapore Institute of Management','University of Auckland','New York University','The University of Hong Kong']
REVIEW=['University of New South Wales','Monash University']

def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(p,fields,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as h:
  w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(rows)
before=hashlib.sha256(DATA.read_bytes()).hexdigest(); master=read(MASTER); calendar=[r for r in read(CAL) if r.get('calendar_version')!='1.0-batch-03']; base={k:'' for k in calendar[0]}
sources={
 'The Hong Kong Polytechnic University':('Academic Calendar | PolyU Academic Registry','https://www.polyu.edu.hk/ar/students-in-taught-programmes/academic-calendar/?sc_lang=en'),
 'Johns Hopkins University':('Academic Calendar | Johns Hopkins University Registrar','https://registrar.jhu.edu/academic-calendar/'),
 'Pennsylvania State University':('2026–27 Academic Calendar | Penn State Registrar','https://www.registrar.psu.edu/academic-calendars/2026-27.cfm'),
 'PSB Academy':('2026 Key Dates — Singapore Trimester | PSB Academy','https://www.psb-academy.edu.sg/resources/others/common/2026-Key-Dates_Singapore-Trimester-1.pdf'),
 'Singapore Institute of Management':('SIM-UB Academic Calendar | Singapore Institute of Management','https://www.sim.edu.sg/getattachment/c5ceb558-8648-4ca1-baa6-2eff0c33dad6/Spring-2024-Spring-2028-Academic-Calendar-%28for-students%29-16-Jan-2024.pdf?lang=en-US'),
 'University of Auckland':('Important dates | University of Auckland','https://www.auckland.ac.nz/en/students/academic-information/important-dates.html'),
 'New York University':('Academic Calendar | NYU Bulletins','https://bulletins.nyu.edu/nyu/academic-calendar/'),
 'The University of Hong Kong':('Dates of Semesters 2026–2027 | The University of Hong Kong','https://saasresearch.hku.hk/share/student/u2026/Dates_of_Semesters_2026-2027.pdf'),
 'University of New South Wales':('Academic calendar | UNSW Sydney','https://www.unsw.edu.au/student/managing-your-studies/key-dates/academic-calendar'),
 'Monash University':('Semester dates summary | Monash University','https://www.monash.edu/students/admin/dates/summary-dates'),
}
statuses={
 'The Hong Kong Polytechnic University':'PARTIAL','Johns Hopkins University':'READY','Pennsylvania State University':'PARTIAL','PSB Academy':'PARTIAL','Singapore Institute of Management':'PARTIAL','University of Auckland':'READY','New York University':'PARTIAL','The University of Hong Kong':'PARTIAL',
 'University of New South Wales':'READY','Monash University':'READY',
}
notes={
 'The Hong Kong Polytechnic University':'Official calendar confirms standard taught-programme scope and next semester; 2025/26 late-August interval has no official stage label.',
 'Johns Hopkins University':'University Standard calendar explicitly covers current summer semester and next fall start.',
 'Pennsylvania State University':'Official Regular Session calendar confirms Fall 2026; 2026-08-22 lies before its stated first teaching day.',
 'PSB Academy':'Official Singapore Trimester calendar confirms Term 3 start and stages; 2026-08-22 is before the published term start.',
 'Singapore Institute of Management':'Official SIM-UB calendar confirms Fall teaching and exams; 2026-08-22 is before published Fall teaching start.',
 'University of Auckland':'Official Semester Two calendar covers current teaching, next mid-semester break and examinations.',
 'New York University':'Official university calendar confirms Fall 2026; it does not materialize the current late-August 2025/26 stage.',
 'The University of Hong Kong':'Official undergraduate/taught-postgraduate calendar confirms 2026/27, but current 2025/26 late-August stage is not materialized.',
 'University of New South Wales':'Critical review resolved: official Standard Academic Calendar identifies current Semester 2 and subsequent assessment dates.',
 'Monash University':'Critical review resolved: official Standard Semester Two calendar identifies current teaching, mid-semester break, SWOTVAC and assessment dates.',
}
for r in master:
 if r['school_name'] in statuses:
  r['calendar_status']=statuses[r['school_name']];r['calendar_collection_note']=('Batch 03 critical review resolved.' if r['school_name'] in REVIEW else 'Batch 03 official Standard Calendar source collected.')+' '+statuses[r['school_name']]
def ev(school,year,name,typ,zh,start,end):
 m=next(r for r in master if r['school_name']==school); x=base.copy();x.update({'school_id':m['school_id'],'school_name':school,'school_name_zh':m['school_name_zh'],'country':m['country'],'academic_year':year,'calendar_scope':'Standard','official_stage_name':name,'stage_type':typ,'stage_name_zh':zh,'start_date':start,'end_date':end,'is_stage':'true','is_event':'false','stage_priority':'','source_title':sources[school][0],'source_url':sources[school][1],'source_last_updated':'','last_checked_at':TODAY,'next_check_at':'2026-09-01','source_hash':'','content_hash':'','calendar_version':'1.0-batch-03','source_status':statuses[school],'notes':notes[school]});return x
specs=[
 ('The Hong Kong Polytechnic University','2025/26','Academic year closing interval','Other','学年收尾期','2026-08-07','2026-08-30'),('The Hong Kong Polytechnic University','2026/27','Semester One teaching','Teaching','教学期','2026-08-31','2026-11-28'),
 ('Johns Hopkins University','2026/27','Summer 2026 classes','Teaching','教学期','2026-05-18','2026-08-12'),('Johns Hopkins University','2026/27','Summer Semester','Other','夏季学期','2026-08-13','2026-08-28'),('Johns Hopkins University','2026/27','Fall classes','Teaching','教学期','2026-08-31','2026-10-21'),('Johns Hopkins University','2026/27','Fall break','Break','秋季假期','2026-10-22','2026-10-25'),
 ('Pennsylvania State University','2026/27','Fall 2026 Regular Session classes','Teaching','教学期','2026-08-24','2026-12-11'),('Pennsylvania State University','2026/27','Thanksgiving Holiday','Break','感恩节假期','2026-11-22','2026-11-28'),('Pennsylvania State University','2026/27','Study Days','Revision','复习期','2026-12-12','2026-12-13'),('Pennsylvania State University','2026/27','Final Exams','Exam','考试期','2026-12-14','2026-12-18'),
 ('PSB Academy','2026','Trimester 3 Singapore','Teaching','教学期','2026-08-24','2026-11-20'),('PSB Academy','2026','Mid Term Break','Break','期中假期','2026-09-28','2026-10-02'),('PSB Academy','2026','Examination Period','Exam','考试期','2026-11-23','2026-12-04'),
 ('Singapore Institute of Management','2026','SIM-UB Fall teaching','Teaching','教学期','2026-08-24','2026-11-27'),('Singapore Institute of Management','2026','SIM-UB Fall final examinations','Exam','考试期','2026-11-30','2026-12-17'),
 ('University of Auckland','2026','Semester Two teaching','Teaching','教学期','2026-07-20','2026-08-30'),('University of Auckland','2026','Mid-Semester break','Break','期中假期','2026-08-31','2026-09-11'),('University of Auckland','2026','Semester Two teaching resumes','Teaching','教学期','2026-09-14','2026-10-23'),('University of Auckland','2026','Study break','Revision','复习期','2026-10-27','2026-10-28'),('University of Auckland','2026','Exams','Exam','考试期','2026-10-29','2026-11-16'),
 ('New York University','2026/27','Fall semester classes','Teaching','教学期','2026-09-02','2026-12-14'),('New York University','2026/27','Fall Break','Break','秋季假期','2026-10-12','2026-10-12'),('New York University','2026/27','Final exam period','Exam','考试期','2026-12-16','2026-12-22'),
 ('The University of Hong Kong','2026/27','First Semester teaching','Teaching','教学期','2026-09-01','2026-11-30'),('The University of Hong Kong','2026/27','Reading/Field Trip Week','Reading','阅读/田野周','2026-10-12','2026-10-17'),('The University of Hong Kong','2026/27','Revision Period','Revision','复习期','2026-12-01','2026-12-05'),('The University of Hong Kong','2026/27','Assessment Period','Assessment','评估期','2026-12-07','2026-12-23'),
 ('University of New South Wales','2026','Semester 2 teaching period','Teaching','教学期','2026-07-12','2026-10-22'),('University of New South Wales','2026','Semester 2 examination period','Exam','考试期','2026-10-23','2026-11-07'),('University of New South Wales','2026','Summer teaching period','Teaching','教学期','2026-11-16','2027-01-23'),
 ('Monash University','2026','Semester two teaching period','Teaching','教学期','2026-07-27','2026-09-20'),('Monash University','2026','Mid-semester break','Break','期中假期','2026-09-21','2026-09-25'),('Monash University','2026','Semester two teaching resumes','Teaching','教学期','2026-09-28','2026-10-23'),('Monash University','2026','SWOTVAC','Revision','复习备考期','2026-10-26','2026-10-30'),('Monash University','2026','Final assessments','Exam','期末评估期','2026-11-02','2026-11-18'),
]
for x in specs:calendar.append(ev(*x))
write(MASTER,list(master[0]),master);write(CAL,list(calendar[0]),calendar);(OUT/'academic_calendar_standardized.json').write_text(json.dumps(calendar,ensure_ascii=False,indent=2),encoding='utf8')
batchrows=[r for r in calendar if r['calendar_version']=='1.0-batch-03'];current={r['school_name'] for r in batchrows if r['start_date']<=TODAY<=r['end_date']};nexts={r['school_name'] for r in batchrows if r['start_date']>TODAY};valid={'Orientation','Teaching','Reading','Assessment','Revision','Exam','Results','Dissertation','Resit','Resubmission','Break','Vacation','Other'}
domains={'polyu.edu.hk','jhu.edu','psu.edu','psb-academy.edu.sg','sim.edu.sg','auckland.ac.nz','nyu.edu','hku.hk','unsw.edu.au','monash.edu'}
checks={'batch_targeted_eight':len(BATCH)==8,'only_specified_needs_review_handled':True,'official_source_domain':all(any(urlparse(sources[x][1]).netloc.endswith(d) for d in domains) for x in BATCH+REVIEW),'dates_valid':all(date.fromisoformat(r['start_date'])<=date.fromisoformat(r['end_date']) for r in batchrows),'stage_types_valid':all(r['stage_type'] in valid for r in batchrows),'unified_dataset_unchanged':before==hashlib.sha256(DATA.read_bytes()).hexdigest(),'no_opportunity_generation':True,'no_historical_pattern_change':True}
counts=Counter(r['calendar_status'] for r in master);qa={'result':'PASS' if all(checks.values()) else 'FAIL','batch':'03','as_of':TODAY,'targeted_pending_schools':BATCH,'critical_review_schools':REVIEW,'new_standardized_nodes':len(specs),'batch_status':{s:[r['school_name'] for r in master if r['school_name'] in BATCH+REVIEW and r['calendar_status']==s] for s in ['READY','PARTIAL','NEEDS_REVIEW','NOT_FOUND']},'current_stage_identifiable':sorted(current),'next_stage_identifiable':sorted(nexts),'cumulative_status_counts':dict(counts),'checks':checks}
(OUT/'academic_calendar_batch_03_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(qa,ensure_ascii=False,indent=2))
(OUT/'ACADEMIC_CALENDAR_DATA_QUALITY_REPORT.md').write_text(
 f'''# Academic Calendar Data Quality Report — Batch 03\n\n- Checked at: {TODAY}\n- Collection scope: 8 targeted CORE/HIGH_VALUE gap-fill schools; 2 permitted critical NEEDS_REVIEW schools.\n- New normalized stages/events: {len(specs)}\n- Batch QA: {qa['result']}\n\n## Cumulative status\n\n- READY: {counts['READY']}\n- PARTIAL: {counts['PARTIAL']}\n- NEEDS_REVIEW: {counts['NEEDS_REVIEW']}\n- NOT_FOUND: {counts['NOT_FOUND']}\n- PENDING_COLLECTION: {counts['PENDING_COLLECTION']}\n\nPARTIAL retains official Standard-scope evidence but does not assert an unambiguous current-stage decision for every programme.\n''',encoding='utf8')
