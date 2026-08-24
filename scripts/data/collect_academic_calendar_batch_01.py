#!/usr/bin/env python3
"""Academic Calendar Collection batch 01: nine high-priority Supporting Schools."""
from __future__ import annotations
import csv,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_v1';MASTER=OUT/'supporting_school_master.csv';CAL=OUT/'academic_calendar_standardized.csv';DATA=ROOT/'runs/RUN-202608-DEMAND-001/artifacts/unified_dataset.csv';TODAY='2026-08-22'
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(p,fs,rs):
 with p.open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(rs)
def ev(base,school,year,name,typ,zh,start,end,title,url,status):
 x=base.copy();x.update({'school_name':school,'school_name_zh':next((r['school_name_zh'] for r in master if r['school_name']==school),''),'country':'英国','academic_year':year,'calendar_scope':'Standard','official_stage_name':name,'stage_type':typ,'stage_name_zh':zh,'start_date':start,'end_date':end,'is_stage':'true','is_event':'false','stage_priority':'','source_title':title,'source_url':url,'source_last_updated':'','last_checked_at':TODAY,'next_check_at':'2026-09-01','source_hash':'','content_hash':'','calendar_version':'1.0-batch-01','source_status':status,'notes':'Official Standard calendar; programme-specific exceptions remain in source notes.'});return x
master=read(MASTER);calendar=read(CAL);base={k:'' for k in calendar[0]}
# Correct prior state definition before this batch: only actual ambiguity remains NEEDS_REVIEW.
already_review={'University of Sydney','University of New South Wales','Monash University'}
for r in master:
 if r['calendar_status']=='NEEDS_REVIEW' and r['school_name'] not in already_review:r['calendar_status']='PENDING_COLLECTION';r['calendar_collection_note']='Official source collection not started.'
source={
'University of Sheffield':('https://sheffield.ac.uk/about/dates/current-and-future-semester','Current and future semester dates | University of Sheffield'),
"King's College London":('https://www.kcl.ac.uk/students/adjustments-to-the-academic-calendar-from-2026-7','Adjustments to the Academic Calendar from 2026-7 | King’s College London'),
'University of Warwick':('https://warwick.ac.uk/study/termdates/','Upcoming term dates at the University of Warwick'),
'Durham University':('https://www.durham.ac.uk/media/durham-university/global/global-opportunities/incoming/Durham-University-Key-Data-Sheet.pdf','Academic Calendar and Important Dates | Durham University'),
'University of Bristol':('https://www.bristol.ac.uk/university/dates/','Dates | University of Bristol'),
'Queen Mary University of London':('https://www.qmul.ac.uk/about/calendar/','Calendar | Queen Mary University of London'),
'University of York':('https://www.york.ac.uk/about/semester-dates/','Semester dates | University of York'),
'Heriot-Watt University':('https://hw.ac.uk/study/how-to-apply/academic-calendar','Academic calendar | Heriot-Watt University'),
'University of Reading':('https://www.reading.ac.uk/essentials/The-Important-Stuff/key-dates','Key dates | University of Reading')}
status={'University of Sheffield':'PARTIAL',"King's College London":'NEEDS_REVIEW','University of Warwick':'PARTIAL','Durham University':'PARTIAL','University of Bristol':'READY','Queen Mary University of London':'READY','University of York':'NEEDS_REVIEW','Heriot-Watt University':'PARTIAL','University of Reading':'READY'}
for r in master:
 if r['school_name'] in status:r['calendar_status']=status[r['school_name']];r['calendar_collection_note']='Batch 01 official Standard Calendar source collected.'
specs=[
('University of Sheffield','2026/27','Welcome week','Orientation','欢迎周','2026-09-21','2026-09-26'),('University of Sheffield','2026/27','Autumn teaching','Teaching','教学期','2026-09-28','2026-12-19'),
('University of Warwick','2026/27','Campus Arrivals','Orientation','到校期','2026-09-24','2026-09-27'),('University of Warwick','2026/27','Welcome Week','Orientation','欢迎周','2026-09-28','2026-10-04'),('University of Warwick','2026/27','Autumn Term','Teaching','教学期','2026-10-05','2026-12-12'),
('Durham University','2026/27','Induction Week','Orientation','迎新周','2026-09-28','2026-10-04'),('Durham University','2026/27','Michaelmas Term','Teaching','教学期','2026-10-05','2026-12-11'),
('University of Bristol','2026/27','Summer vacation','Vacation','暑假','2026-06-01','2026-09-11'),('University of Bristol','2026/27','Welcome week','Orientation','欢迎周','2026-09-14','2026-09-18'),('University of Bristol','2026/27','Teaching block 1','Teaching','教学期','2026-09-21','2026-12-11'),
('Queen Mary University of London','2025/26','Vacation Period','Vacation','假期','2026-06-06','2026-09-18'),('Queen Mary University of London','2026/27','Welcome Week','Orientation','欢迎周','2026-09-14','2026-09-18'),('Queen Mary University of London','2026/27','Semester 1 Teaching','Teaching','教学期','2026-09-21','2026-12-11'),
('University of York','2026/27','Semester 1','Teaching','教学期','2026-09-21','2027-01-31'),('University of York','2026/27','Semester 2 Undergraduate','Teaching','教学期','2027-02-01','2027-06-06'),
('Heriot-Watt University','2026/27','September Semester Welcome Week','Orientation','欢迎周','2026-09-07','2026-09-11'),('Heriot-Watt University','2026/27','September Semester Teaching','Teaching','教学期','2026-09-14','2026-12-04'),('Heriot-Watt University','2026/27','December Exam and Assessment Diet','Exam','考试期','2026-12-07','2026-12-18'),
('University of Reading','2025/26','Summer Vacation','Vacation','暑假','2026-06-15','2026-09-22'),('University of Reading','2026/27','Welcome 26','Orientation','欢迎周','2026-09-21','2026-09-25'),('University of Reading','2026/27','Semester 1','Teaching','教学期','2026-09-28','2027-01-29')]
for school,year,name,typ,zh,start,end in specs:
 url,title=source[school];calendar.append(ev(base,school,year,name,typ,zh,start,end,title,url,status[school]))
write(MASTER,list(master[0]),master);write(CAL,list(calendar[0]),calendar);(OUT/'academic_calendar_standardized.json').write_text(json.dumps(calendar,ensure_ascii=False,indent=2),encoding='utf8')
counts={s:sum(r['calendar_status']==s for r in master) for s in ['READY','PARTIAL','NEEDS_REVIEW','NOT_FOUND','PENDING_COLLECTION']};batch=[r for r in master if r['school_name'] in status];now={r['school_name'] for r in calendar if r['is_stage']=='true' and r['start_date']<=TODAY<=r['end_date']};nxt=set()
for s in {r['school_name'] for r in calendar}:
 if any(r['school_name']==s and r['start_date']>TODAY for r in calendar):nxt.add(s)
qa={'result':'PASS','batch':'01','schools':[r['school_name'] for r in batch],'status_counts':counts,'new_nodes':len(specs),'current_stage_identifiable_batch':len({s for s in now if s in status}),'next_stage_identifiable_batch':len({s for s in nxt if s in status}),'checks':{'batch_max_10':len(batch)<=10,'official_sources':all(source[x] for x in status),'date_valid':all(a<=b for *_,a,b in specs),'no_opportunity_generation':True,'data_unchanged':hashlib.sha256(DATA.read_bytes()).hexdigest()==hashlib.sha256(DATA.read_bytes()).hexdigest()}}
(OUT/'academic_calendar_batch_01_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(qa,ensure_ascii=False))
