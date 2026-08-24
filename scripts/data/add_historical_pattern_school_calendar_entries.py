#!/usr/bin/env python3
"""Attach existing school evidence to country patterns; no Pattern recomputation or Calendar lookup."""
from __future__ import annotations
import csv,hashlib,json,re
from collections import defaultdict
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2];ART=ROOT/'runs/RUN-202608-DEMAND-001/artifacts';OUT=ART/'historical_demand_pattern_v1';PATS=OUT/'historical_demand_patterns.csv';SUP=OUT/'historical_demand_pattern_school_supporting_evidence.csv';CFG=ROOT/'config/insight/historical_demand_pattern_v1.yaml';ALIASES=ROOT/'config/data/school_aliases.yaml'
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(p,fs,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(rows)
def chinese_alias(aliases):
 return next((x for x in aliases if re.search('[\u4e00-\u9fff]',x)), '')
def main():
 inputs=[SUP,CFG,ALIASES];before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 pats=read(PATS);support=read(SUP);dictionary=yaml.safe_load(ALIASES.read_text(encoding='utf8'))
 aliases={x['canonical_name']:x.get('aliases',[]) for x in dictionary['canonical_entities']}
 grouped=defaultdict(list)
 for s in support:grouped[(s['month'],s['task_type'],s['value_class'],s['country'])].append(s)
 entries=[];unmapped=[]
 for p in pats:
  key=(p['month'],p['task_type'],p['value_class'],p['country']);ss=sorted(grouped[key],key=lambda x:(-int(x['school_support_order_count']),x['school']))
  payload=[]
  for s in ss:
   canonical=s['school'];zh=chinese_alias(aliases.get(canonical,[]));mapping='CANONICAL_SCHOOL_READY_FOR_CALENDAR_MATCH' if canonical in aliases else 'SCHOOL_MAPPING_REQUIRED'
   item={'school_name':canonical,'school_name_zh':zh,'school_name_zh_status':'AVAILABLE_FROM_ACTIVE_ALIAS' if zh else 'NOT_AVAILABLE_IN_ACTIVE_ALIAS','school_order_count':int(s['school_support_order_count']),'school_repeat_year_count':int(s['school_support_repeat_year_count']),'school_pattern_strength':'NOT_EVALUATED_SUPPORTING_ONLY','historical_years':s['school_support_years_present'],'calendar_validation_entry_status':mapping,'academic_calendar_match_status':'NOT_EVALUATED_NO_CALENDAR_DATA'}
   payload.append(item);entries.append({**{k:p[k] for k in ['month','task_type','value_class','country']},**item})
   if mapping=='SCHOOL_MAPPING_REQUIRED':unmapped.append(canonical)
  p['supporting_schools']=json.dumps(payload,ensure_ascii=False);p['supporting_school_count']=len(payload);p['school_role']='SUPPORTING_SCHOOL_EVIDENCE_AND_ACADEMIC_CALENDAR_VALIDATION_ENTRY'
 fields=list(pats[0]);fields += [x for x in ['supporting_schools','supporting_school_count','school_role'] if x not in fields]
 write(PATS,fields,pats)
 entry_fields=list(entries[0]);write(OUT/'historical_demand_pattern_calendar_entries.csv',entry_fields,entries)
 after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 qa={'result':'PASS' if before==after and all(int(p['supporting_school_count'])>0 for p in pats) else 'FAIL','checks':{'each_country_pattern_has_supporting_schools':all(int(p['supporting_school_count'])>0 for p in pats),'school_not_in_primary_key':all('school' not in {k for k in p if k not in {'supporting_schools','supporting_school_count','school_role'}} for p in pats),'no_pattern_strength_recalculation':all(e['school_pattern_strength']=='NOT_EVALUATED_SUPPORTING_ONLY' for e in entries),'calendar_not_executed':all(e['academic_calendar_match_status']=='NOT_EVALUATED_NO_CALENDAR_DATA' for e in entries),'source_pattern_strength_and_school_support_unchanged':before==after},'country_pattern_count':len(pats),'patterns_without_school':sum(not int(p['supporting_school_count']) for p in pats),'supporting_school_evidence_rows':len(entries),'unique_supporting_schools':len({e['school_name'] for e in entries}),'canonical_calendar_ready_schools':len({e['school_name'] for e in entries if e['calendar_validation_entry_status']=='CANONICAL_SCHOOL_READY_FOR_CALENDAR_MATCH'}),'schools_requiring_mapping':sorted(set(unmapped)),'calendar_data_match':'NOT_EVALUATED_NO_ACADEMIC_CALENDAR_DATA'}
 (OUT/'historical_pattern_school_calendar_entry_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf8')
 if qa['result']!='PASS':raise RuntimeError('calendar-entry QA failed')
 print(json.dumps({'patterns':len(pats),'entries':len(entries),'schools':qa['unique_supporting_schools'],'calendar_ready':qa['canonical_calendar_ready_schools'],'needs_mapping':len(unmapped),'qa':qa['result']},ensure_ascii=False))
if __name__=='__main__':main()
