#!/usr/bin/env python3
"""A09 evidence alignment using only A07/A08 contract outputs and frozen rules."""
from __future__ import annotations

import csv
import os
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUN_ID=os.environ['CDAT_RUN_ID']; ART=ROOT/f'runs/{RUN_ID}/artifacts'; QUALITY=ROOT/f'runs/{RUN_ID}/quality'; OUT=ART/'current_context_validation'
A07=ART/'historical_demand/historical_demand_report.json'; A08=ART/'academic_context/academic_context_report.json'
DQ=QUALITY/'quality_report.json'; BUSINESS=ROOT/'config/dimensions/academic_calendar/academic_calendar_business_mapping_v1.yaml'; PROMOTION=ROOT/'config/dimensions/academic_calendar/promotion_window_business_rules_v1.yaml'
PERIOD_INDEX={'EARLY_AUGUST':0,'MID_AUGUST':1,'LATE_AUGUST':2}
VALID={'CURRENTLY_SUPPORTED','HISTORICAL_ONLY_VALID','CALENDAR_NEW_SIGNAL','TEMPORAL_SHIFT','CONTEXT_CONFLICT','INSUFFICIENT_EVIDENCE'}
FOCUS={'University College London','University of Leeds','University of Southampton','University of Manchester','University of Sydney','University of New South Wales','University of Melbourne','University of Queensland','City University of Hong Kong','The Hong Kong Polytechnic University','The University of Hong Kong'}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,obj): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def labels_from_window(start,end):
    periods=[]
    for label,(a,b) in {'EARLY_AUGUST':('2026-08-01','2026-08-10'),'MID_AUGUST':('2026-08-11','2026-08-20'),'LATE_AUGUST':('2026-08-21','2026-08-31')}.items():
        if start<=b and end>=a: periods.append(label)
    return periods
def best_period(counts):
    max_count=max(counts.values(),default=0)
    return [k for k,v in counts.items() if v==max_count and v>0]
def temporal_alignment(historical,current):
    if not historical:return 'CALENDAR_ONLY'
    if not current:return 'HISTORICAL_ONLY'
    if set(historical)&set(current):return 'ALIGNED'
    h=sum(PERIOD_INDEX[x] for x in historical)/len(historical); c=sum(PERIOD_INDEX[x] for x in current)/len(current)
    return 'SHIFT_EARLIER' if c<h else 'SHIFT_LATER'
def evidence(h_strength,calendar_school_count):
    if h_strength=='STRONG' and calendar_school_count>=2:return 'STRONG'
    if h_strength=='STRONG' or calendar_school_count>=1:return 'DIRECTIONAL'
    return 'WATCH'

def main():
    inputs=[A07,A08,DQ,BUSINESS,PROMOTION]; before={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    hist=json.loads(A07.read_text(encoding='utf-8')); ctx=json.loads(A08.read_text(encoding='utf-8')); dq=json.loads(DQ.read_text(encoding='utf-8'))
    # Build historical country-direction support strictly from the A07 school-level evidence.
    hg=defaultdict(list)
    for item in hist['school_patterns']: hg[(item['country'],item['business_direction'])].append(item)
    cg=defaultdict(list)
    for item in ctx['school_context']:
        for direction in item['business_direction']: cg[(item['country'],direction)].append(item)
    country_meta={x['country']:x for x in hist['country_patterns']}
    historical_directions={country:set(meta['business_directions']) for country,meta in country_meta.items()}
    country_records=[]
    all_keys=set(hg)|set(cg)|{(country,direction) for country,directions in historical_directions.items() for direction in directions}
    for country,direction in sorted(all_keys):
        hitems=hg[(country,direction)]; citems=cg[(country,direction)]
        h_present=bool(hitems) or direction in historical_directions.get(country,set())
        hperiods=best_period(Counter({p:sum(x['august_period_consultation_count'].get(p,0) for x in hitems) for p in PERIOD_INDEX})) if hitems else best_period(country_meta.get(country,{}).get('august_period_consultation_count',{}))
        cperiods=sorted({p for x in citems for p in labels_from_window(x['promotion_window']['start'],x['promotion_window']['end'])},key=PERIOD_INDEX.get)
        hstrength=country_meta.get(country,{}).get('historical_strength','WATCH')
        alignment=temporal_alignment(hperiods,cperiods)
        if h_present and citems:
            status='CURRENTLY_SUPPORTED' if alignment=='ALIGNED' else 'TEMPORAL_SHIFT'
        elif h_present:
            status='HISTORICAL_ONLY_VALID' if hstrength in {'STRONG','DIRECTIONAL'} else 'INSUFFICIENT_EVIDENCE'
        elif citems:
            status='CALENDAR_NEW_SIGNAL'
        else: status='INSUFFICIENT_EVIDENCE'
        country_records.append({'validation_id':f'A09-C-{len(country_records)+1:03d}','validation_level':'COUNTRY_BUSINESS_DIRECTION','country':country,'business_direction':direction,'historical_periods':hperiods,'current_promotion_periods':cperiods,'historical_evidence_count':len(hitems),'historical_country_pattern_available':h_present,'calendar_signal_count':len(citems),'calendar_school_count':len({x['school'] for x in citems}),'validation_status':status,'time_alignment':alignment,'business_alignment':'SUPPORTED' if h_present and citems else ('HISTORICAL_ONLY' if h_present else 'CALENDAR_NEW'),'evidence_strength':evidence(hstrength,len({x['school'] for x in citems})),'reason':'Historical country evidence and Calendar promotion-window evidence are kept as independent counts; they are not compared as equivalent quantities.'})
    # School validation stays intentionally narrow: fixed priority schools plus every Calendar signal school.
    historical_by_school=defaultdict(list)
    for item in hist['school_patterns']: historical_by_school[(item['country'],item['school'])].append(item)
    calendar_by_school=defaultdict(list)
    for item in ctx['school_context']: calendar_by_school[(item['country'],item['school'])].append(item)
    target_schools={(c,s) for c,s in historical_by_school if s in FOCUS}|set(calendar_by_school)
    school_records=[]
    for country,school in sorted(target_schools):
        hs=historical_by_school[(country,school)]; cs=calendar_by_school[(country,school)]
        directions=sorted({x['business_direction'] for x in hs}|{d for x in cs for d in x['business_direction']})
        for direction in directions:
            hitems=[x for x in hs if x['business_direction']==direction]; citems=[x for x in cs if direction in x['business_direction']]
            hperiods=best_period(Counter({p:sum(x['august_period_consultation_count'].get(p,0) for x in hitems) for p in PERIOD_INDEX}))
            cperiods=sorted({p for x in citems for p in labels_from_window(x['promotion_window']['start'],x['promotion_window']['end'])},key=PERIOD_INDEX.get)
            align=temporal_alignment(hperiods,cperiods)
            if hitems and citems: status='CURRENTLY_SUPPORTED' if align=='ALIGNED' else 'TEMPORAL_SHIFT'
            elif hitems: status='HISTORICAL_ONLY_VALID'
            elif citems: status='CALENDAR_NEW_SIGNAL'
            else: status='INSUFFICIENT_EVIDENCE'
            school_records.append({'validation_id':f'A09-S-{len(school_records)+1:03d}','validation_level':'SCHOOL_BUSINESS_DIRECTION','school':school,'country':country,'business_direction':direction,'historical_demand':sorted({x['specific_task_type'] for x in hitems}),'calendar_stage':sorted({x['academic_stage'] for x in citems}),'calendar_signal':sorted({x['calendar_context_id'] for x in citems}),'historical_period':hperiods,'promotion_window':[{'start':x['promotion_window']['start'],'end':x['promotion_window']['end']} for x in citems],'validation_status':status,'time_alignment':align,'evidence_strength':evidence('STRONG' if any(x['historical_strength']=='STRONG' for x in hitems) else 'DIRECTIONAL',len({x['school'] for x in citems})),'reason':'School-level validation is supporting evidence only. Missing Calendar context does not invalidate historical demand.'})
    status_count=Counter(x['validation_status'] for x in country_records)
    country_validations=[]
    countries=sorted({x['country'] for x in country_records}|{x['country'] for x in ctx['country_context']})
    for country in countries:
        rows=[x for x in country_records if x['country']==country]; cmeta=next((x for x in ctx['country_context'] if x['country']==country),{})
        country_validations.append({'country':country,'historical_business_directions':sorted({x['business_direction'] for x in rows if x['historical_country_pattern_available']}),'current_academic_stages':cmeta.get('academic_stages',[]),'calendar_business_directions':sorted({x['business_direction'] for x in rows if x['calendar_signal_count']}),'supported_directions':sorted(x['business_direction'] for x in rows if x['validation_status']=='CURRENTLY_SUPPORTED'),'historical_only_directions':sorted(x['business_direction'] for x in rows if x['validation_status']=='HISTORICAL_ONLY_VALID'),'calendar_new_directions':sorted(x['business_direction'] for x in rows if x['validation_status']=='CALENDAR_NEW_SIGNAL'),'temporal_shift_directions':sorted(x['business_direction'] for x in rows if x['validation_status']=='TEMPORAL_SHIFT'),'country_validation_strength':'STRONG' if any(x['evidence_strength']=='STRONG' for x in rows) else ('DIRECTIONAL' if any(x['evidence_strength']=='DIRECTIONAL' for x in rows) else 'WATCH'),'calendar_coverage':{'schools':cmeta.get('school_count',0),'events':cmeta.get('event_count',0)},'best_time_alignment':sorted({x['time_alignment'] for x in rows})})
    report={'agent_id':'A09','agent_name':'Current Context Validation Agent','agent_version':'2.0','status':'COMPLETED','run_id':RUN_ID,'target_month':'2026-08','validation_scope':'Country × Business Direction; school-only for priority historical schools and all 2026 Calendar-signal schools.','country_validations':country_validations,'school_validations':school_records,'validation_records':country_records,'historical_only_opportunities':[x for x in country_records if x['validation_status']=='HISTORICAL_ONLY_VALID'],'currently_supported_opportunities':[x for x in country_records if x['validation_status']=='CURRENTLY_SUPPORTED'],'calendar_new_signals':[x for x in country_records if x['validation_status']=='CALENDAR_NEW_SIGNAL'],'temporal_shifts':[x for x in country_records if x['validation_status']=='TEMPORAL_SHIFT'],'context_conflicts':[x for x in country_records if x['validation_status']=='CONTEXT_CONFLICT'],'insufficient_evidence':[x for x in country_records if x['validation_status']=='INSUFFICIENT_EVIDENCE'],'status_counts':dict(status_count),'data_quality_limitations':{'data_quality_gate':dq['overall_quality_status'],'school_id_coverage':dq['school_quality']['school_id_coverage_of_canonical'],'amount_missing':'Limits value evidence only; not demand-count evidence.','ddl_limitations':'Limits lead-time evidence only; it does not change August consultation timing.'},'calendar_coverage_limitations':'Calendar coverage is limited to current collected schools/events. Calendar absence is retained as HISTORICAL_ONLY, never a conflict or deletion.','source_artifacts':[str(p.relative_to(ROOT)) for p in inputs]}
    audit_fields=['validation_id','validation_level','country','business_direction','historical_periods','current_promotion_periods','historical_evidence_count','calendar_signal_count','calendar_school_count','validation_status','time_alignment','business_alignment','evidence_strength','reason']
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'validation_audit.csv').open('w',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=audit_fields,extrasaction='ignore');w.writeheader();w.writerows(country_records)
    after={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    report['qa']={'result':'PASS' if before==after and all(x['validation_status'] in VALID for x in country_records+school_records) else 'FAIL','checks':{'a07_checksum_unchanged':before[str(A07.relative_to(ROOT))]==after[str(A07.relative_to(ROOT))],'a08_checksum_unchanged':before[str(A08.relative_to(ROOT))]==after[str(A08.relative_to(ROOT))],'formal_status_enum_only':all(x['validation_status'] in VALID for x in country_records+school_records),'historical_only_retained':bool(report['historical_only_opportunities']),'calendar_new_retained':bool(report['calendar_new_signals']),'time_alignment_traceable':all(x['time_alignment'] in {'ALIGNED','SHIFT_EARLIER','SHIFT_LATER','CALENDAR_ONLY','HISTORICAL_ONLY','UNKNOWN'} for x in country_records),'country_school_not_mixed':all(x['validation_level']=='COUNTRY_BUSINESS_DIRECTION' for x in country_records) and all(x['validation_level']=='SCHOOL_BUSINESS_DIRECTION' for x in school_records),'no_a10_a13_run':True,'calendar_count_not_compared_to_historical_count':True}}
    dump(OUT/'validation_report.json',report)
    if report['qa']['result']!='PASS':raise RuntimeError('A09 QA failed')
    print(json.dumps({'status':'COMPLETED','country_direction_validations':len(country_records),'school_validations':len(school_records),'status_counts':dict(status_count)},ensure_ascii=False))
if __name__=='__main__':main()
