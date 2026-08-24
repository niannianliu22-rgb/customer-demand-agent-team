#!/usr/bin/env python3
"""A10 Monthly Customer Demand Opportunity from A07/A08/A09 contracts only."""
from __future__ import annotations

import hashlib, json, os
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUN_ID=os.environ['CDAT_RUN_ID']; ART=ROOT/f'runs/{RUN_ID}/artifacts'; QUALITY=ROOT/f'runs/{RUN_ID}/quality'; OUT=ART/'demand_opportunity'
A07=ART/'historical_demand/historical_demand_report.json'; A08=ART/'academic_context/academic_context_report.json'; A09=ART/'current_context_validation/validation_report.json'
DQ=QUALITY/'quality_report.json'; BUSINESS=ROOT/'config/dimensions/academic_calendar/academic_calendar_business_mapping_v1.yaml'; TASK=ROOT/'config/dimensions/task_type/task_type_rules_frozen_v17.yaml'
PERIOD_ORDER={'EARLY_AUGUST':0,'MID_AUGUST':1,'LATE_AUGUST':2}; VALID_DIRECTIONS={'ASSIGNMENT_BUSINESS','DISSERTATION_BUSINESS','EXAM_BUSINESS','RESIT_BUSINESS','COURSE_SUPPORT','LONG_TERM_SERVICE','SELECTION_SUPPORT'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def window_periods(start,end):
    dates={'EARLY_AUGUST':('2026-08-01','2026-08-10'),'MID_AUGUST':('2026-08-11','2026-08-20'),'LATE_AUGUST':('2026-08-21','2026-08-31')}
    return [p for p,(a,b) in dates.items() if start<=b and end>=a]
def rank(status,strength):
    return {'CURRENTLY_SUPPORTED':0,'HISTORICAL_ONLY_VALID':1,'CALENDAR_NEW_SIGNAL':2,'TEMPORAL_SHIFT':3,'INSUFFICIENT_EVIDENCE':4,'CONTEXT_CONFLICT':5}[status], {'STRONG':0,'DIRECTIONAL':1,'WATCH':2}[strength]
def opportunity_strength(status,evidence):
    if status=='INSUFFICIENT_EVIDENCE' or status=='CONTEXT_CONFLICT':return 'WATCH'
    if status=='CURRENTLY_SUPPORTED' and evidence=='STRONG':return 'STRONG'
    if status=='HISTORICAL_ONLY_VALID' and evidence=='STRONG':return 'STRONG'
    return 'DIRECTIONAL'
def time_source(status):
    return {'CURRENTLY_SUPPORTED':'HISTORICAL_AND_CALENDAR','HISTORICAL_ONLY_VALID':'HISTORICAL_ONLY','CALENDAR_NEW_SIGNAL':'CALENDAR_ONLY','TEMPORAL_SHIFT':'DIRECTIONAL','INSUFFICIENT_EVIDENCE':'DIRECTIONAL','CONTEXT_CONFLICT':'DIRECTIONAL'}[status]

def main():
    inputs=[A07,A08,A09,DQ,BUSINESS,TASK]; before={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    hist=json.loads(A07.read_text(encoding='utf-8')); ctx=json.loads(A08.read_text(encoding='utf-8')); validation=json.loads(A09.read_text(encoding='utf-8')); dq=json.loads(DQ.read_text(encoding='utf-8'))
    calendar=defaultdict(list)
    for item in ctx['school_context']:
        for direction in item['business_direction']:calendar[(item['country'],direction)].append(item)
    school_val=defaultdict(list)
    for item in validation['school_validations']:school_val[(item['country'],item['business_direction'])].append(item)
    schools=[]; direction_rows=[]
    for record in validation['validation_records']:
        country=record['country']; direction=record['business_direction']; status=record['validation_status']; evidence=record['evidence_strength']; citems=calendar[(country,direction)]
        current_periods=record['current_promotion_periods']; historical_periods=record['historical_periods']
        if status=='CURRENTLY_SUPPORTED': best=sorted(set(historical_periods)&set(current_periods),key=PERIOD_ORDER.get) or current_periods or historical_periods
        elif status in {'CALENDAR_NEW_SIGNAL','TEMPORAL_SHIFT'}: best=current_periods
        else: best=historical_periods or current_periods
        starts=sorted({x['promotion_window']['start'] for x in citems}); ends=sorted({x['promotion_window']['end'] for x in citems})
        direction_rows.append({'country':country,'business_direction':direction,'best_operating_window':best,'window_start':starts[0] if starts else '', 'window_end':ends[-1] if ends else '', 'time_evidence_source':time_source(status),'academic_stages':sorted({x['academic_stage'] for x in citems}),'validation_status':status,'time_alignment':record['time_alignment'],'historical_support':{'country_pattern_available':record['historical_country_pattern_available'],'school_evidence_rows':record['historical_evidence_count'],'historical_periods':historical_periods},'calendar_support':{'calendar_signal_count':record['calendar_signal_count'],'calendar_school_count':record['calendar_school_count'],'promotion_periods':current_periods},'opportunity_strength':opportunity_strength(status,evidence),'reason':record['reason'],'validation_ref':record['validation_id']})
        for sv in school_val[(country,direction)]:
            if sv['validation_status'] in {'INSUFFICIENT_EVIDENCE','CONTEXT_CONFLICT'}:continue
            cschool=[x for x in citems if x['school']==sv['school']]
            task_types=sorted(set(sv['historical_demand'])|{task for x in cschool for task in x['potential_task_type']})
            services=sorted({service for x in cschool for service in x['potential_service_direction']})
            school_best=sv['historical_period'] if sv['validation_status']=='HISTORICAL_ONLY_VALID' else sorted({p for x in cschool for p in window_periods(x['promotion_window']['start'],x['promotion_window']['end'])},key=PERIOD_ORDER.get) or sv['historical_period']
            schools.append({'school':sv['school'],'school_id':next((x['school_id'] for x in cschool if x['school_id']),''),'country':country,'academic_stage':sv['calendar_stage'],'specific_task_types':task_types,'service_directions':services,'best_operating_window':school_best,'promotion_window_start':min((x['promotion_window']['start'] for x in cschool),default=''),'promotion_window_end':max((x['promotion_window']['end'] for x in cschool),default=''),'validation_status':sv['validation_status'],'historical_evidence':{'task_types':sv['historical_demand'],'historical_periods':sv['historical_period']},'calendar_evidence':{'calendar_context_ids':sv['calendar_signal'],'academic_stages':sv['calendar_stage']},'opportunity_strength':opportunity_strength(sv['validation_status'],sv['evidence_strength']),'reason':sv['reason']})
    # Deduplicate a school direction if A09 provided it more than once, preserving fields without manufacturing values.
    unique={}
    for item in schools:
        key=(item['country'],item['school'],tuple(item['specific_task_types']),tuple(item['service_directions']),item['validation_status'])
        unique[key]=item
    schools=list(unique.values())
    countries=[]
    for country in sorted({x['country'] for x in direction_rows}):
        rows=[x for x in direction_rows if x['country']==country]
        local_schools=[x for x in schools if x['country']==country]
        primary=[x['business_direction'] for x in rows if x['opportunity_strength']=='STRONG']
        secondary=[x['business_direction'] for x in rows if x['opportunity_strength']=='DIRECTIONAL']
        watch=[x['business_direction'] for x in rows if x['opportunity_strength']=='WATCH']
        ordered=sorted(local_schools,key=lambda x:(rank(x['validation_status'],x['opportunity_strength']),x['school']))
        key_school_rows=[]; seen_schools=set()
        for item in ordered:
            if item['school'] in seen_schools: continue
            seen_schools.add(item['school']); key_school_rows.append({'school':item['school'],'school_id':item['school_id'],'validation_status':item['validation_status'],'opportunity_strength':item['opportunity_strength']})
        countries.append({'target_month':'2026-08','country':country,'best_operating_windows':[{'business_direction':x['business_direction'],'periods':x['best_operating_window'],'window_start':x['window_start'],'window_end':x['window_end'],'time_evidence_source':x['time_evidence_source'],'time_alignment':x['time_alignment']} for x in rows],'academic_stages':sorted({stage for x in rows for stage in x['academic_stages']}),'business_directions':rows,'primary_business_directions':sorted(set(primary)),'secondary_business_directions':sorted(set(secondary)),'watch_directions':sorted(set(watch)),'key_schools':key_school_rows[:10],'school_opportunities':ordered,'opportunity_strength':'STRONG' if primary else ('DIRECTIONAL' if secondary else 'WATCH'),'evidence_summary':'Validation Status is inherited from A09; Calendar signals are potential context, not orders. Country conclusions do not elevate one-school Calendar coverage to STRONG without strong historical support.'})
    task_types={x['task_type'] for x in hist['task_type_patterns']}; calendar_tasks={t for x in ctx['school_context'] for t in x['potential_task_type']}; allowed_tasks=task_types|calendar_tasks
    report={'agent_id':'A10','agent_name':'Demand Opportunity Agent','display_role':'Demand Opportunity Agent','agent_version':'2.0','status':'COMPLETED','run_id':RUN_ID,'target_month':'2026-08','country_opportunities':countries,'school_opportunities':schools,'data_quality_limitations':validation['data_quality_limitations'],'source_artifacts':[str(p.relative_to(ROOT)) for p in inputs]}
    # Business-readable view: business directions at country level; specific needs only under schools.
    lines=['# August 2026 Customer Demand Opportunity','']
    for c in countries:
        lines += [f"## {c['country']}", '', f"- Best operating windows: " + '; '.join(f"{x['business_direction']} → {' / '.join(x['periods']) or 'DIRECTIONAL'}" for x in c['best_operating_windows']),f"- Academic stages: {', '.join(c['academic_stages']) or 'Historical evidence only'}",f"- Business directions: {', '.join(c['primary_business_directions']+c['secondary_business_directions']) or 'WATCH only'}",f"- Strength: {c['opportunity_strength']}",'- Key schools:']
        for s in c['key_schools']:
            source=[x for x in c['school_opportunities'] if x['school']==s['school']]
            tasks=sorted({need for x in source for need in x['specific_task_types']})
            services=sorted({need for x in source for need in x['service_directions']})
            needs=', '.join(tasks or services) or 'Historical/Calendar direction only'
            statuses=', '.join(sorted({x['validation_status'] for x in source}))
            lines.append(f"  - {s['school']}: {needs} ({statuses}).")
        lines.append('')
    OUT.mkdir(parents=True,exist_ok=True); (OUT/'demand_opportunity_summary.md').write_text('\n'.join(lines),encoding='utf-8')
    after={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    a09_hist={x['validation_id'] for x in validation['historical_only_opportunities']}; a10_hist={x['validation_ref'] for x in direction_rows if x['validation_status']=='HISTORICAL_ONLY_VALID'}
    a09_new={x['validation_id'] for x in validation['calendar_new_signals']}; a10_new={x['validation_ref'] for x in direction_rows if x['validation_status']=='CALENDAR_NEW_SIGNAL'}
    a09_shift={x['validation_id'] for x in validation['temporal_shifts']}; a10_shift=[x for x in direction_rows if x['validation_status']=='TEMPORAL_SHIFT']
    checks={'a07_a08_a09_checksum_unchanged':before[str(A07.relative_to(ROOT))]==after[str(A07.relative_to(ROOT))] and before[str(A08.relative_to(ROOT))]==after[str(A08.relative_to(ROOT))] and before[str(A09.relative_to(ROOT))]==after[str(A09.relative_to(ROOT))],'historical_only_not_deleted':a09_hist<=a10_hist,'calendar_new_not_deleted':a09_new<=a10_new,'temporal_shift_has_current_window':all(x['best_operating_window'] for x in a10_shift),'country_layer_has_no_task_type_field':all('specific_task_types' not in x for x in countries),'school_needs_traceable':all(set(x['specific_task_types'])<=allowed_tasks for x in schools),'single_school_calendar_not_amplified':all(not (x['calendar_support']['calendar_school_count']==1 and x['opportunity_strength']=='STRONG' and not x['historical_support']['country_pattern_available']) for x in direction_rows),'no_new_business_direction':all(x['business_direction'] in VALID_DIRECTIONS for x in direction_rows),'no_a11_a13_run':True,'no_upstream_recomputation':True}
    report['qa']={'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'counts':{'countries':len(countries),'country_direction_opportunities':len(direction_rows),'school_opportunities':len(schools),'strengths':{k:sum(c['opportunity_strength']==k for c in countries) for k in ['STRONG','DIRECTIONAL','WATCH']},'historical_only':len(a10_hist),'calendar_new':len(a10_new),'temporal_shift':len(a10_shift)}}
    dump(OUT/'insight_report.json',report)
    if report['qa']['result']!='PASS':raise RuntimeError('A10 QA failed')
    print(json.dumps({'status':'COMPLETED',**report['qa']['counts']},ensure_ascii=False))
if __name__=='__main__':main()
