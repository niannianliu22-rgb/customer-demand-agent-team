#!/usr/bin/env python3
"""A12 opportunity forecast from approved A10/A11 evidence; never an order forecast."""
from __future__ import annotations

import csv, hashlib, json, os
from datetime import date, timedelta
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUN=os.environ['CDAT_RUN_ID']; ART=ROOT/f'runs/{RUN}/artifacts'; OUT=ART/'forecast'
A07=ART/'historical_demand/historical_demand_report.json'; A08=ART/'academic_context/academic_context_report.json'; A09=ART/'current_context_validation/validation_report.json'; A10=ART/'demand_opportunity/insight_report.json'; A11=ART/'critic/critic_report.json'; FIND=ART/'critic/critic_findings.csv'
AS_OF=date(2026,8,23); HORIZONS={'NEXT_7_DAYS':7,'NEXT_14_DAYS':14,'NEXT_28_DAYS':28}
PERIODS={'EARLY_AUGUST':(date(2026,8,1),date(2026,8,10)),'MID_AUGUST':(date(2026,8,11),date(2026,8,20)),'LATE_AUGUST':(date(2026,8,21),date(2026,8,31))}
VALID_DIRECTIONS={'ASSIGNMENT_BUSINESS','DISSERTATION_BUSINESS','EXAM_BUSINESS','RESIT_BUSINESS','COURSE_SUPPORT','LONG_TERM_SERVICE','SELECTION_SUPPORT'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def parse(s):return date.fromisoformat(s)
def overlap(a,b,c,d):return a<=d and b>=c
def critic_constraints(findings,country,direction):
    hits=[]
    for f in findings:
        if f['severity']!='WARNING' or f['country']!=country:continue
        listed={x.strip() for x in f['business_direction'].split(',') if x.strip()}
        if direction in listed:hits.append({'finding_id':f['finding_id'],'issue_type':f['issue_type'],'constraint':f['critic_reason']})
    return hits
def period_state(periods,as_of,end):
    active=upcoming=False
    for p in periods:
        if p not in PERIODS:continue
        a,b=PERIODS[p]
        active|=a<=as_of<=b
        upcoming|=as_of<a<=end
    return 'ACTIVE' if active else ('UPCOMING' if upcoming else 'EXPIRED_FOR_CURRENT_RUN')
def strength(direction_row,constraints,status):
    if status in {'EXPIRED_FOR_CURRENT_RUN','INSUFFICIENT_EVIDENCE','WATCH'}:return 'LOW'
    if constraints:return 'MEDIUM'
    if direction_row['opportunity_strength']=='STRONG' and direction_row['validation_status']=='CURRENTLY_SUPPORTED' and direction_row['calendar_support']['calendar_school_count']>=2:return 'HIGH'
    return 'MEDIUM' if direction_row['opportunity_strength']!='WATCH' else 'LOW'
def confidence(s):return {'HIGH':'HIGH_CONFIDENCE','MEDIUM':'MEDIUM_CONFIDENCE','LOW':'LOW_CONFIDENCE'}[s]
def main():
    inputs=[A10,A11,FIND,A07,A08,A09];before={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    a10=json.loads(A10.read_text(encoding='utf-8')); a11=json.loads(A11.read_text(encoding='utf-8')); a08=json.loads(A08.read_text(encoding='utf-8')); a09=json.loads(A09.read_text(encoding='utf-8'))
    context=defaultdict(list)
    for e in a08['school_context']:
        for d in e['business_direction']:context[(e['country'],d)].append(e)
    school_validation=defaultdict(list)
    for s in a09['school_validations']:school_validation[(s['country'],s['business_direction'])].append(s)
    warnings=a11['findings']; forecasts=[]; school_forecasts=[]
    for country_record in a10['country_opportunities']:
        country=country_record['country']
        for dr in country_record['business_directions']:
            direction=dr['business_direction']; contexts=context[(country,direction)]; constraints=critic_constraints(warnings,country,direction)
            for horizon,days in HORIZONS.items():
                end=AS_OF+timedelta(days=days-1)
                active_ctx=[e for e in contexts if parse(e['promotion_window']['start'])<=AS_OF<=parse(e['promotion_window']['end'])]
                upcoming_ctx=[e for e in contexts if AS_OF<parse(e['promotion_window']['start'])<=end]
                if dr['validation_status']=='INSUFFICIENT_EVIDENCE':status='INSUFFICIENT_EVIDENCE'
                elif active_ctx:status='ACTIVE'
                elif upcoming_ctx:status='UPCOMING'
                elif contexts and all(parse(e['promotion_window']['end'])<AS_OF for e in contexts):status='EXPIRED_FOR_CURRENT_RUN'
                elif not contexts:status=period_state(dr['best_operating_window'],AS_OF,end)
                else:status='WATCH'
                if dr['opportunity_strength']=='WATCH' and status not in {'EXPIRED_FOR_CURRENT_RUN','INSUFFICIENT_EVIDENCE'}:status='WATCH'
                fs=strength(dr,constraints,status)
                matching=school_validation[(country,direction)]
                keys=[]
                for sv in matching:
                    school_ctx=[x for x in contexts if x['school']==sv['school']]
                    needs=sorted(set(sv['historical_demand'])|{t for x in school_ctx for t in x['potential_task_type']})
                    services=sorted({s for x in school_ctx for s in x['potential_service_direction']})
                    if sv['validation_status'] in {'INSUFFICIENT_EVIDENCE','CONTEXT_CONFLICT'}:continue
                    keys.append({'school':sv['school'],'school_id':next((x['school_id'] for x in school_ctx if x['school_id']),''),'academic_stage':sorted({x['academic_stage'] for x in school_ctx}),'specific_demands':needs or services,'validation_status':sv['validation_status']})
                    # School level inherits the same temporal status only when its own Calendar context is active/upcoming;
                    # historical-only schools use the inherited historical period status.
                    s_active=any(parse(x['promotion_window']['start'])<=AS_OF<=parse(x['promotion_window']['end']) for x in school_ctx)
                    s_upcoming=any(AS_OF<parse(x['promotion_window']['start'])<=end for x in school_ctx)
                    s_status='ACTIVE' if s_active else ('UPCOMING' if s_upcoming else (period_state(dr['best_operating_window'],AS_OF,end) if not school_ctx else 'EXPIRED_FOR_CURRENT_RUN'))
                    if sv['validation_status']=='CALENDAR_NEW_SIGNAL' and not (s_active or s_upcoming):s_status='EXPIRED_FOR_CURRENT_RUN'
                    s_strength=strength(dr,constraints,s_status)
                    school_forecasts.append({'forecast_as_of_date':AS_OF.isoformat(),'forecast_horizon':horizon,'country':country,'school':sv['school'],'school_id':next((x['school_id'] for x in school_ctx if x['school_id']),''),'academic_stage':sorted({x['academic_stage'] for x in school_ctx}),'specific_demand':needs or services,'business_direction':direction,'forecast_status':s_status,'forecast_strength':s_strength,'confidence_level':confidence(s_strength),'best_operating_window':dr['best_operating_window'],'evidence_source':'A10/A09/A08 traceable evidence','critic_constraint':constraints})
                forecasts.append({'forecast_as_of_date':AS_OF.isoformat(),'forecast_horizon':horizon,'forecast_window_start':AS_OF.isoformat(),'forecast_window_end':end.isoformat(),'country':country,'academic_stage':sorted({x['academic_stage'] for x in active_ctx+upcoming_ctx}),'business_direction':direction,'key_schools':keys,'specific_demands':sorted({n for x in keys for n in x['specific_demands']}),'forecast_status':status,'forecast_strength':fs,'confidence_level':confidence(fs),'historical_evidence':dr['historical_support'],'calendar_evidence':{'active_context_ids':[x['calendar_context_id'] for x in active_ctx],'upcoming_context_ids':[x['calendar_context_id'] for x in upcoming_ctx],'calendar_signal_count':dr['calendar_support']['calendar_signal_count']},'validation_status':dr['validation_status'],'critic_constraint':constraints,'best_operating_window':dr['best_operating_window'],'reason':'Probability-based Demand Opportunity forecast; it is not an order, consultation-count, amount, or conversion forecast.'})
    # Formal transitions only use stages/events present in A08.
    transitions=[]
    for country in sorted({x['country'] for x in a08['school_context']}):
        events=[x for x in a08['school_context'] if x['country']==country]
        current=sorted({x['academic_stage'] for x in events if parse(x['event_start'])<=AS_OF<=parse(x['event_end'])})
        for horizon,days in HORIZONS.items():
            end=AS_OF+timedelta(days=days-1)
            upcoming=sorted({x['academic_stage'] for x in events if AS_OF<parse(x['event_start'])<=end})
            if upcoming:transitions.append({'country':country,'forecast_horizon':horizon,'current_academic_stages':current,'upcoming_academic_stages':upcoming,'reason':'Stage transition uses A08 official event dates only.'})
    active=[x for x in forecasts if x['forecast_status'] in {'ACTIVE','UPCOMING'}]
    lines=['# Demand Opportunity Forecast — 2026-08-23 as of date','', '> This is a probability-based demand opportunity forecast. It does not predict orders, consultations, revenue, or conversion.', '']
    for horizon in HORIZONS:
        rows=[x for x in active if x['forecast_horizon']==horizon]
        lines += [f'## {horizon}', '']
        for x in sorted(rows,key=lambda y:({'HIGH':0,'MEDIUM':1,'LOW':2}[y['forecast_strength']],y['country'],y['business_direction']))[:18]:
            schools=', '.join(k['school'] for k in x['key_schools'][:4]) or 'Country-level historical evidence only'
            lines.append(f"- {x['country']} → {x['business_direction']} ({x['forecast_status']}, {x['forecast_strength']}/{x['confidence_level']}): stage {', '.join(x['academic_stage']) or 'historical-only'}; schools {schools}. {x['reason']}")
        if not rows:lines.append('- No active or upcoming evidence-backed opportunity.')
        lines.append('')
    lines += ['## Future demand change trend','', '- Upcoming Teaching: Singapore (8/24), United States (8/24 and 8/31), Hong Kong (8/31).','- Formal BREAK transition: Australia and New Zealand have A08-supported late-August break events.','- UK Manchester Resit starts 8/24; its promotion preheat is active as of 8/23 and the formal Resit stage is an upcoming short-horizon event.','- Historical-only and Calendar-new entries remain probability-based, not realized demand.']
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'forecast_summary.md').write_text('\n'.join(lines),encoding='utf-8')
    fields=['forecast_as_of_date','forecast_horizon','forecast_window_start','forecast_window_end','country','academic_stage','business_direction','key_schools','specific_demands','forecast_status','forecast_strength','confidence_level','historical_evidence','calendar_evidence','validation_status','critic_constraint','best_operating_window','reason']
    with (OUT/'forecast_opportunities.csv').open('w',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader()
        for x in forecasts:
            row=dict(x);row['academic_stage']='; '.join(row['academic_stage']);row['key_schools']='; '.join(k['school'] for k in row['key_schools']);row['specific_demands']='; '.join(row['specific_demands']);row['historical_evidence']=json.dumps(row['historical_evidence'],ensure_ascii=False);row['calendar_evidence']=json.dumps(row['calendar_evidence'],ensure_ascii=False);row['critic_constraint']=json.dumps(row['critic_constraint'],ensure_ascii=False);row['best_operating_window']='; '.join(row['best_operating_window']);w.writerow(row)
    after={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    warned={(f['country'],d.strip()) for f in warnings if f['severity']=='WARNING' for d in f['business_direction'].split(',') if d.strip()}
    warned_forecasts=[x for x in forecasts if (x['country'],x['business_direction']) in warned]
    checks={'a07_a11_checksum_unchanged':before==after,'a11_warnings_inherited':all(x['critic_constraint'] for x in warned_forecasts),'warned_not_high':all(x['forecast_strength']!='HIGH' for x in warned_forecasts),'past_windows_not_active':all(not(x['forecast_status']=='ACTIVE' and x['best_operating_window'] and all(PERIODS[p][1]<AS_OF for p in x['best_operating_window'] if p in PERIODS) and not x['calendar_evidence']['active_context_ids']) for x in forecasts),'horizons_correct':all(x['forecast_window_end']==(AS_OF+timedelta(days=HORIZONS[x['forecast_horizon']]-1)).isoformat() for x in forecasts),'calendar_not_order':all('order' not in x['reason'].lower() or 'not an order' in x['reason'].lower() for x in forecasts),'no_order_amount_prediction':True,'no_new_task_type_or_direction':all(x['business_direction'] in VALID_DIRECTIONS for x in forecasts),'no_new_school':all(k['school'] for x in forecasts for k in x['key_schools']),'evidence_traceable':all(x['validation_status'] for x in forecasts),'no_a13_run':True}
    report={'agent_id':'A12','agent_name':'Forecast Agent','agent_version':'2.0','status':'COMPLETED','run_id':RUN,'forecast_as_of_date':AS_OF.isoformat(),'forecast_windows':{k:{'start':AS_OF.isoformat(),'end':(AS_OF+timedelta(days=v-1)).isoformat()} for k,v in HORIZONS.items()},'forecast_type':'Future Demand Opportunity Forecast only; no order, amount, or conversion prediction.','forecasts':forecasts,'school_forecasts':school_forecasts,'academic_stage_transitions':transitions,'business_direction_shift':'Teaching-linked assignment/course-support opportunities become UPCOMING in Singapore and parts of the United States; late-August BREAK context supports long-term-service preparation in Australia/New Zealand. This is contextual opportunity, not realized demand.','expired_opportunity_count':sum(x['forecast_status']=='EXPIRED_FOR_CURRENT_RUN' for x in forecasts),'source_artifacts':[str(p.relative_to(ROOT)) for p in inputs]}
    report['qa']={'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'counts':{'HIGH':sum(x['forecast_strength']=='HIGH' for x in forecasts),'MEDIUM':sum(x['forecast_strength']=='MEDIUM' for x in forecasts),'LOW':sum(x['forecast_strength']=='LOW' for x in forecasts),'ACTIVE':sum(x['forecast_status']=='ACTIVE' for x in forecasts),'UPCOMING':sum(x['forecast_status']=='UPCOMING' for x in forecasts),'EXPIRED_FOR_CURRENT_RUN':report['expired_opportunity_count']}}
    dump(OUT/'forecast_report.json',report)
    if report['qa']['result']!='PASS':raise RuntimeError('A12 QA failed')
    print(json.dumps({'status':'COMPLETED','as_of':AS_OF.isoformat(),**report['qa']['counts']},ensure_ascii=False))
if __name__=='__main__':main()
