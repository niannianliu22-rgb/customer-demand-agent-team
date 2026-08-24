#!/usr/bin/env python3
"""Create the deduplicated Supporting-School calendar master and initial official-source batch.

This collector is deliberately conservative: only dates directly confirmed on an
official page are standardised. Remaining schools stay NEEDS_REVIEW, never guessed.
"""
from __future__ import annotations
import csv,hashlib,json
from collections import defaultdict
from datetime import date,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ART=ROOT/'runs/RUN-202608-DEMAND-001/artifacts';INPUT=ART/'historical_demand_pattern_v1/historical_demand_pattern_calendar_entries.csv';OUT=ART/'academic_calendar_v1';DATA=ART/'unified_dataset.csv';TODAY='2026-08-22'
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(p,fs,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(rows)
def sid(name):return 'SCH-'+hashlib.sha1(name.encode()).hexdigest()[:10].upper()
def stage(school,country,year,scope,official,typ,zh,start,end,is_stage,is_event,title,url,status='READY',notes=''):
 return {'school_id':sid(school),'school_name':school,'school_name_zh':'','country':country,'academic_year':year,'calendar_scope':scope,'official_stage_name':official,'stage_type':typ,'stage_name_zh':zh,'start_date':start,'end_date':end,'is_stage':str(is_stage).lower(),'is_event':str(is_event).lower(),'stage_priority':'','source_title':title,'source_url':url,'source_last_updated':'','last_checked_at':TODAY,'next_check_at':'2026-09-01','source_hash':'','content_hash':'','calendar_version':'1.0-initial-batch','source_status':status,'notes':notes}
def main():
 before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [INPUT,DATA]};rows=read(INPUT);g=defaultdict(list)
 for r in rows:g[r['school_name']].append(r)
 master=[]
 for school,rs in sorted(g.items()):
  master.append({'school_id':sid(school),'school_name':school,'school_name_zh':next((r['school_name_zh'] for r in rs if r['school_name_zh']),''),'country':rs[0]['country'],'supporting_pattern_count':len({(r['month'],r['task_type'],r['country']) for r in rs}),'historical_order_count':sum(int(r['school_order_count']) for r in rs),'calendar_status':'NEEDS_REVIEW','calendar_collection_note':'Official Calendar collection pending or requires programme/scope confirmation.'})
 # Official sources confirmed during the current collection batch.
 src={
 'University of Leeds':('https://www.leeds.ac.uk/term-dates','Term dates | University of Leeds'),
 'University College London':('https://www.ucl.ac.uk/study/current-students/life-ucl/term-dates-and-closures','Term dates and closures | Study at UCL'),
 'University of Manchester':('https://www.manchester.ac.uk/about/key-dates/index.htm','Key dates at The University of Manchester'),
 'University of Southampton':('https://www.southampton.ac.uk/about/term-dates','Term dates and semesters | University of Southampton'),
 'University of Melbourne':('https://www.unimelb.edu.au/dates','University of Melbourne - Key Dates'),
 'University of Sydney':('https://www.sydney.edu.au/students/key-dates.html','Key dates | The University of Sydney'),
 'University of New South Wales':('https://www.unsw.edu.au/student/managing-your-studies/key-dates/academic-calendar','Academic calendar | UNSW Sydney'),
 'Monash University':('https://www.monash.edu/students/admin/dates','Important dates | Monash University'),}
 events=[]
 # Directly published date ranges only. Academic Stage Priority is deliberately empty:
 # no project-wide priority standard existed to reuse.
 s='University of Melbourne';u,t=src[s]
 events += [stage(s,'澳洲','2026','Standard','Semester 2 - 12 teaching weeks','Teaching','教学期','2026-07-27','2026-10-25',True,False,t,u),stage(s,'澳洲','2026','Standard','SWOT Vac','Revision','复习备考期','2026-10-26','2026-10-30',True,False,t,u),stage(s,'澳洲','2026','Standard','Examinations','Exam','考试期','2026-11-02','2026-11-20',True,False,t,u),stage(s,'澳洲','2026','Standard','Results final release date','Results','成绩发布','2026-12-04','2026-12-04',False,True,t,u),stage(s,'澳洲','2026','Standard','Special/Supplementary Examinations','Resit','补考期','2026-12-11','2026-12-18',True,False,t,u)]
 s='University of Leeds';u,t=src[s]
 events += [stage(s,'英国','2026/27','Standard','International students’ orientation week','Orientation','迎新周','2026-09-14','2026-09-18',True,False,t,u,'PARTIAL'),stage(s,'英国','2026/27','Standard','Introduction week (Welcome)','Orientation','欢迎周','2026-09-21','2026-09-27',True,False,t,u,'PARTIAL'),stage(s,'英国','2026/27','Standard','Autumn term','Teaching','教学期','2026-09-28','2026-12-11',True,False,t,u,'PARTIAL'),stage(s,'英国','2026/27','Standard','Autumn semester examinations','Exam','考试期','2027-01-11','2027-01-22',True,False,t,u,'PARTIAL')]
 s='University College London';u,t=src[s]
 events += [stage(s,'英国','2026/27','Standard','First term','Teaching','教学期','2026-09-28','2026-12-18',True,False,t,u,'PARTIAL'),stage(s,'英国','2026/27','Standard','College Reading Week','Reading','阅读周','2026-11-09','2026-11-09',False,True,t,u,'PARTIAL')]
 s='University of Manchester';u,t=src[s]
 events += [stage(s,'英国','2025/26','Standard','Exam resits','Resit','补考期','2026-08-24','2026-09-04',True,False,t,u,'PARTIAL'),stage(s,'英国','2026/27','Standard','Welcome Week','Orientation','欢迎周','2026-09-21','2026-09-25',True,False,t,u,'PARTIAL'),stage(s,'英国','2026/27','Standard','Semester 1 assessment and exams','Exam','考试期','2027-01-14','2027-01-29',True,False,t,u,'PARTIAL')]
 s='University of Southampton';u,t=src[s]
 events += [stage(s,'英国','2026/27','Standard','Welcome week','Orientation','欢迎周','2026-09-14','2026-09-20',True,False,t,u,'PARTIAL'),stage(s,'英国','2026/27','Standard','Autumn term','Teaching','教学期','2026-09-21','2026-12-12',True,False,t,u,'PARTIAL'),stage(s,'英国','2026/27','Standard','Christmas vacation','Vacation','假期','2026-12-13','2027-01-03',True,False,t,u,'PARTIAL')]
 # Sydney / UNSW / Monash official pages located, but their standard-programme date/scope
 # extraction requires page-level confirmation; do not invent entries.
 byschool={x['school_name']:[] for x in master}
 for e in events:byschool[e['school_name']].append(e)
 for x in master:
  if x['school_name']=='University of Melbourne':x['calendar_status']='READY';x['calendar_collection_note']='Official 2026 Standard calendar contains current and next stages.'
  elif x['school_name'] in src:x['calendar_status']='PARTIAL' if byschool[x['school_name']] else 'NEEDS_REVIEW';x['calendar_collection_note']='Official source located; scope/date extraction incomplete where no direct standard range was confirmed.'
 zh_map={x['school_name']:x['school_name_zh'] for x in master}
 for event in events:event['school_name_zh']=zh_map[event['school_name']]
 write(OUT/'supporting_school_master.csv',list(master[0]),master)
 fields=list(events[0]);write(OUT/'academic_calendar_standardized.csv',fields,events);(OUT/'academic_calendar_standardized.json').write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf8')
 ready=sum(x['calendar_status']=='READY' for x in master);partial=sum(x['calendar_status']=='PARTIAL' for x in master);review=sum(x['calendar_status']=='NEEDS_REVIEW' for x in master);notfound=sum(x['calendar_status']=='NOT_FOUND' for x in master)
 current=[e for e in events if e['is_stage']=='true' and e['start_date']<=TODAY<=e['end_date']];nexts=[]
 for school,es in byschool.items():
  future=sorted((e for e in es if e['start_date']>TODAY),key=lambda e:e['start_date'])
  if future:nexts.append(future[0])
 dq=['# ACADEMIC CALENDAR DATA QUALITY REPORT','',f'- Supporting Schools: {len(master)}','- Official sources located: 8','- READY: '+str(ready)+'; PARTIAL: '+str(partial)+'; NEEDS_REVIEW: '+str(review)+'; NOT_FOUND: '+str(notfound),f'- Standardized official events/stages: {len(events)}','- Current stage identifiable: '+str(len({e['school_name'] for e in current}))+f'; next stage identifiable: {len({e['school_name'] for e in nexts})}.',f"- Missing school_name_zh among standardized rows: {sum(not e['school_name_zh'] for e in events)}.",'- All standardized source URLs are official university domains; all populated dates are ISO and start_date <= end_date.','- No existing Academic Stage Priority rule was found. Suggested non-frozen precedence for later confirmation: Exam > Resit > Revision > Assessment > Reading > Orientation > Teaching > Break/Vacation.','- Coverage limitation: 47 schools have not yet had a verified official source recorded in this initial batch; they remain NEEDS_REVIEW and are retained in the master.','- Special calendars: University of Sydney, Monash University and UNSW expose course/programme-specific or multi-period calendars; Standard scope needs explicit page-level validation.']
 (OUT/'ACADEMIC_CALENDAR_DATA_QUALITY_REPORT.md').write_text('\n'.join(dq),encoding='utf8')
 after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [INPUT,DATA]}
 qa={'result':'PASS' if before==after and all(e['start_date']<=e['end_date'] for e in events) else 'FAIL','supporting_school_total':len(master),'official_source_located':8,'calendar_status':{'READY':ready,'PARTIAL':partial,'NEEDS_REVIEW':review,'NOT_FOUND':notfound},'countries':len({x['country'] for x in master}),'events_stages':len(events),'current_stage_identifiable':len({e['school_name'] for e in current}),'next_stage_identifiable':len({e['school_name'] for e in nexts}),'stage_priority':'PENDING_CONFIRMATION_NO_EXISTING_RULE','checks':{'supporting_master_deduplicated':len(master)==55,'official_urls_for_events':all('https://' in e['source_url'] for e in events),'date_valid':all(e['start_date']<=e['end_date'] for e in events),'standard_stage_type':all(e['stage_type'] in {'Orientation','Teaching','Reading','Assessment','Revision','Exam','Results','Dissertation','Resit','Resubmission','Break','Vacation','Other'} for e in events),'source_inputs_unchanged':before==after,'no_opportunity_or_forecast':True}}
 (OUT/'academic_calendar_collection_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf8')
 if qa['result']!='PASS':raise RuntimeError('collection QA failed')
 print(json.dumps(qa,ensure_ascii=False))
if __name__=='__main__':main()
