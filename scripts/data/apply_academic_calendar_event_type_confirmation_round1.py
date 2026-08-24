#!/usr/bin/env python3
"""Apply approved Event Type Round 1 as a versioned V1.1 confirmation layer."""
from __future__ import annotations

import csv, hashlib, json
from collections import Counter, defaultdict
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]
IN=ROOT/'runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_standardization_v1/academic_calendar_standardized.csv'
OUT=ROOT/'runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_event_type_confirmation_v1'
CFG=ROOT/'config/dimensions/academic_calendar'
OLD_SCHEMA=ROOT/'schemas/academic_calendar_schema_v1.json'; NEW_SCHEMA=ROOT/'schemas/academic_calendar_schema_v1_1.json'
OUT.mkdir(parents=True,exist_ok=True)
VERSION='1.1'; TODAY='2026-08-22'
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(p,fields,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as h:
  w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(rows)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

before=sha(IN); rows=read(IN); old_schema=json.loads(OLD_SCHEMA.read_text(encoding='utf-8'))
compat={'audit_name':'academic_calendar_schema_compatibility_review_round1','input_schema':str(OLD_SCHEMA.relative_to(ROOT)),'input_schema_version':old_schema['schema_version'],'proposed_schema_version':VERSION,'change':'Add nullable/required record_role with canonical values ACADEMIC_EVENT and PERIOD_METADATA to the independent Calendar Canonical Layer.','compatibility':'COMPATIBLE_ADDITIVE_VERSIONED_CHANGE','frozen_v1_preserved':True,'requires_new_schema':True,'result':'PASS'}
(OUT/'academic_calendar_schema_compatibility_review.json').write_text(json.dumps(compat,ensure_ascii=False,indent=2),encoding='utf-8')

schema=json.loads(json.dumps(old_schema));schema['schema_version']=VERSION;schema['status']='FROZEN';schema['previous_schema_version']='1.0';schema['change_summary']='Added record_role to separate Calendar academic events from period metadata.';schema['fields'].append({'name':'record_role','type':'string','required':True,'allowed_values':['ACADEMIC_EVENT','PERIOD_METADATA']})
NEW_SCHEMA.write_text(json.dumps(schema,ensure_ascii=False,indent=2),encoding='utf-8')

overrides={
 'December Exam and Assessment Diet':{'event_type':'EXAM','event_subtype':'EXAM_AND_ASSESSMENT','record_role':'ACADEMIC_EVENT','reason':'Approved: exam-led composite period; retained as one record.'},
 'Revision and examination period':{'event_type':'EXAM','event_subtype':'REVISION_AND_EXAM','record_role':'ACADEMIC_EVENT','reason':'Approved: continuous revision-plus-examination period; not split.'},
 'Semester 1 assessment and exams':{'event_type':'EXAM','event_subtype':'ASSESSMENT_AND_EXAM','record_role':'ACADEMIC_EVENT','reason':'Approved: exam-led composite period; retained as one record.'},
 'Teaching and Assessment weeks - Term 1':{'event_type':'ASSESSMENT','event_subtype':'TEACHING_AND_ASSESSMENT','record_role':'ACADEMIC_EVENT','reason':'Approved: combined teaching and assessment period.'},
 'Teaching and assessment weeks - Term 2':{'event_type':'ASSESSMENT','event_subtype':'TEACHING_AND_ASSESSMENT','record_role':'ACADEMIC_EVENT','reason':'Approved: combined teaching and assessment period.'},
 'Teaching and assessment weeks - Term 3':{'event_type':'ASSESSMENT','event_subtype':'TEACHING_AND_ASSESSMENT','record_role':'ACADEMIC_EVENT','reason':'Approved: combined teaching and assessment period.'},
 'Academic year closing interval':{'event_type':'OTHER','event_subtype':'','record_role':'PERIOD_METADATA','reason':'Approved: Academic Period Metadata; excluded from Calendar → Demand Mapping.'},
 'Summer Semester':{'event_type':'OTHER','event_subtype':'','record_role':'PERIOD_METADATA','reason':'Approved: period metadata; excluded from Calendar → Demand Mapping.'},
}
confirmation={'event_type_confirmation_round':'1','rule_version':VERSION,'status':'FROZEN','scope':'Level-1 event_type confirmation and approved mixed-semantic subtype overrides only.','taxonomy':'KEEP_AS_IS','approved_event_types':['ORIENTATION','TEACHING','READING','ASSESSMENT','REVISION','EXAM','RESULTS','RESIT','BREAK','VACATION','OTHER'],'approved_overrides':[{'event_name_original':name,**value} for name,value in overrides.items()],'record_role_policy':{'ACADEMIC_EVENT':'Eligible Calendar event role; Mapping is not executed by this confirmation.','PERIOD_METADATA':'Retained calendar evidence and period context; excluded from any future Calendar → Demand Mapping.'},'prohibited':['demand_mapping','opportunity_generation','full_subtype_taxonomy_refinement']}
(CFG/'calendar_event_type_manual_confirmation_round1_v1_1.yaml').write_text(yaml.safe_dump(confirmation,allow_unicode=True,sort_keys=False),encoding='utf-8')

out=[]
for r in rows:
 x=dict(r); rule=overrides.get(x['event_name_original']);x['record_role']='ACADEMIC_EVENT'
 if rule:x['event_type']=rule['event_type'];x['event_subtype']=rule['event_subtype'];x['record_role']=rule['record_role']
 x['event_type_confirmation_version']=VERSION;x['event_type_confirmation_status']='APPROVED';out.append(x)
fields=list(out[0]);write(OUT/'academic_calendar_standardized_v1_1.csv',fields,out)

by_type=defaultdict(list);by_raw=defaultdict(list)
for r in out:by_type[r['event_type']].append(r);by_raw[(r['event_type'],r['event_name_original'])].append(r)
summary=[]
for typ in sorted(by_type):
 g=by_type[typ];summary.append({'event_type':typ,'record_count':len(g),'record_share':f'{len(g)/len(out)*100:.2f}%','unique_event_name_count':len({r['event_name_original'] for r in g}),'school_count':len({r['school'] for r in g}),'countries':'; '.join(sorted({r['country'] for r in g})),'manual_decision':'APPROVED','manual_note':'Round 1 confirmed; taxonomy retained.'})
write(OUT/'event_type_manual_confirmation_round1.csv',list(summary[0]),summary)
raw_review=[]
for (typ,name),g in sorted(by_raw.items()):
 rule=overrides.get(name);raw_review.append({'event_type':typ,'event_name_original':name,'record_count':len(g),'schools':'; '.join(sorted({r['school'] for r in g})),'countries':'; '.join(sorted({r['country'] for r in g})),'event_subtype':g[0]['event_subtype'],'record_role':g[0]['record_role'],'manual_decision':'APPROVED','manual_note':rule['reason'] if rule else 'Approved through Level-1 event_type confirmation.'})
write(OUT/'event_type_raw_event_confirmation_round1.csv',list(raw_review[0]),raw_review)

source_by_id={r['calendar_record_id']:r for r in rows}; changed=[]
for r in out:
 old=source_by_id[r['calendar_record_id']]
 if old['event_type']!=r['event_type'] or old['event_subtype']!=r['event_subtype'] or r['record_role']!='ACADEMIC_EVENT':changed.append(r['calendar_record_id'])
checks={'schema_compatibility_pass':compat['result']=='PASS','records_unchanged':len(rows)==len(out)==118,'event_type_taxonomy_unchanged':set(r['event_type'] for r in out)==set(confirmation['approved_event_types']),'approved_raw_events':len(raw_review)==105,'review_required_zero':all(r['event_type_confirmation_status']=='APPROVED' for r in out),'period_metadata_exactly_two':sum(r['record_role']=='PERIOD_METADATA' for r in out)==2,'other_academic_event_zero':sum(r['event_type']=='OTHER' and r['record_role']=='ACADEMIC_EVENT' for r in out)==0,'event_type_conflict_zero':all(len({r['event_type'] for r in g})==1 for g in by_raw.values()),'source_calendar_v1_unchanged':before==sha(IN),'no_demand_mapping':True,'no_opportunity_generation':True}
qa={'audit_name':'academic_calendar_event_type_manual_confirmation_round1','result':'PASS' if all(checks.values()) else 'FAIL','version':VERSION,'counts':{'records':len(out),'event_types':len(by_type),'approved_raw_events':len(raw_review),'review_required':0,'period_metadata':sum(r['record_role']=='PERIOD_METADATA' for r in out),'other_remaining_academic_events':sum(r['event_type']=='OTHER' and r['record_role']=='ACADEMIC_EVENT' for r in out),'changed_records_from_v1':len(changed)},'checks':checks,'source_sha256':before,'output_sha256':sha(OUT/'academic_calendar_standardized_v1_1.csv')}
(OUT/'event_type_manual_confirmation_round1_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
metadata={'calendar_event_type_confirmation_version':VERSION,'status':'FROZEN' if qa['result']=='PASS' else 'CANDIDATE','base_calendar_standardization_version':'1.0','schema':str(NEW_SCHEMA.relative_to(ROOT)),'rules':str((CFG/'calendar_event_type_manual_confirmation_round1_v1_1.yaml').relative_to(ROOT)),'qa_result':qa['result'],'counts':qa['counts'],'source_calendar_frozen_v1_preserved':True}
(OUT/'event_type_manual_confirmation_round1.metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
md=f'''# Academic Calendar Event Type Manual Confirmation — Round 1\n\n- Status: {metadata['status']}\n- Canonical event types: {len(by_type)}\n- Approved raw event names: {len(raw_review)}\n- REVIEW_REQUIRED: 0\n- PERIOD_METADATA records: {qa['counts']['period_metadata']}\n- Remaining OTHER Academic Events: {qa['counts']['other_remaining_academic_events']}\n- QA: {qa['result']}\n\nThe V1 source layer remains unchanged. This V1.1 confirmation layer applies only the approved mixed-semantic subtype values and record_role. No Calendar → Demand Mapping or Opportunity Generation was executed.\n'''
(OUT/'event_type_manual_confirmation_round1_summary.md').write_text(md,encoding='utf-8')
print(json.dumps(qa,ensure_ascii=False,indent=2))
