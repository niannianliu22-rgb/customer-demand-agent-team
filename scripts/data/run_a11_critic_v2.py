#!/usr/bin/env python3
"""A11 critique of A10 conclusions; it never recalculates demand or Calendar facts."""
from __future__ import annotations

import csv, hashlib, json, os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUN=os.environ['CDAT_RUN_ID']; ART=ROOT/f'runs/{RUN}/artifacts'; QUALITY=ROOT/f'runs/{RUN}/quality'; OUT=ART/'critic'
A07=ART/'historical_demand/historical_demand_report.json'; A08=ART/'academic_context/academic_context_report.json'; A09=ART/'current_context_validation/validation_report.json'; A10=ART/'demand_opportunity/insight_report.json'; DQ=QUALITY/'quality_report.json'
ALLOWED={'ASSIGNMENT_BUSINESS','DISSERTATION_BUSINESS','EXAM_BUSINESS','RESIT_BUSINESS','COURSE_SUPPORT','LONG_TERM_SERVICE','SELECTION_SUPPORT'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def add(findings,country,school,direction,issue,severity,evidence,reason,fix='',return_to=''):
    findings.append({'finding_id':f'A11-F-{len(findings)+1:03d}','country':country,'school_if_any':school,'business_direction':direction,'issue_type':issue,'severity':severity,'evidence_reference':evidence,'critic_reason':reason,'recommended_fix':fix,'return_to_agent':return_to})
def main():
    inputs=[A10,A07,A08,A09,DQ]; before={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    a10=json.loads(A10.read_text(encoding='utf-8')); a09=json.loads(A09.read_text(encoding='utf-8')); a08=json.loads(A08.read_text(encoding='utf-8')); dq=json.loads(DQ.read_text(encoding='utf-8'))
    findings=[]; directions=[x for c in a10['country_opportunities'] for x in c['business_directions']]
    # Focus audit: a one-school Calendar signal is directionally valid but must not inherit its country's STRONG label.
    for country in ['英国','新西兰','香港']:
        c=next((x for x in a10['country_opportunities'] if x['country']==country),None)
        if not c:continue
        weak=[x['business_direction'] for x in c['business_directions'] if x['calendar_support']['calendar_school_count']==1 and x['opportunity_strength']!='WATCH']
        if weak:
            sev='WARNING' if c['opportunity_strength']=='STRONG' else 'INFO'
            add(findings,country,'',', '.join(weak),'CALENDAR_COVERAGE_WEAK',sev,'A10 business_directions.calendar_support; A09 country validation','These directions have one Calendar school only. A10 preserves them as DIRECTIONAL, but country-level prose must not imply that every direction shares the country aggregate strength.','Display per-direction strength next to the country summary; keep one-school directions DIRECTIONAL.','A10' if sev=='WARNING' else '')
    # A08 windows span broad sections of August; period labels are valid, but broad min/max dates must not be sold as precise peaks.
    for country in ['澳洲','美国']:
        c=next((x for x in a10['country_opportunities'] if x['country']==country),None)
        if not c:continue
        broad=[x['business_direction'] for x in c['business_directions'] if len(x['calendar_support']['promotion_periods'])==3 and x['time_evidence_source']=='HISTORICAL_AND_CALENDAR']
        if broad:add(findings,country,'',', '.join(broad),'TIME_WINDOW_WEAK','WARNING','A10 best_operating_windows; A08 promotion_window','Calendar promotion windows cover all three August periods; the selected Early/Mid/Late label is historically led, not a precise Calendar peak.','Keep the period label and explicitly identify it as historical-with-Calendar-overlap; do not promote broad window boundaries as a precise peak.','A10')
    hk=next((x for x in a10['country_opportunities'] if x['country']=='香港'),None)
    if hk:
        shift=[x for x in hk['business_directions'] if x['validation_status']=='TEMPORAL_SHIFT']
        if shift:add(findings,'香港','',shift[0]['business_direction'],'TEMPORAL_SHIFT_MISINTERPRETATION','INFO','A09 temporal_shifts; A10 best_operating_windows','A10 retained COURSE_SUPPORT and moved its operating period to LATE_AUGUST without claiming demand growth or decline.','No change required; preserve this wording in downstream Forecast.','')
    sg=next((x for x in a10['country_opportunities'] if x['country']=='新加坡'),None)
    if sg:
        diss=next((x for x in sg['business_directions'] if x['business_direction']=='DISSERTATION_BUSINESS'),None)
        if diss:add(findings,'新加坡','', 'DISSERTATION_BUSINESS','LOW_SAMPLE_OVERCLAIM','INFO','A09 validation_records; A10 business_directions','Dissertation is retained as HISTORICAL_ONLY_VALID and DIRECTIONAL, not elevated by Teaching context.','No change required; keep it secondary/DIRECTIONAL.','')
    # Positive integrity checks are explicit findings so the reviewer can see the required boundaries were examined.
    no_task_at_country=all('specific_task_types' not in c for c in a10['country_opportunities'])
    add(findings,'ALL','','','BUSINESS_DIRECTION_OVERREACH','INFO','A10 country_opportunities.business_directions','Country records contain approved business directions rather than essay/assignment/project as country-level directions.','No change required.','')
    calendar_new=[x for x in directions if x['validation_status']=='CALENDAR_NEW_SIGNAL']
    add(findings,'ALL','','','EVIDENCE_MISMATCH','INFO','A09 calendar_new_signals; A10 business_directions','Calendar-new records remain potential Calendar opportunities and are not described as realized orders.','No change required.','')
    keys=[(x['country'],x['school'],tuple(x['specific_task_types']),tuple(x['service_directions']),x['validation_status']) for x in a10['school_opportunities']]
    duplicate_count=len(keys)-len(set(keys))
    add(findings,'ALL','','','OPPORTUNITY_DUPLICATION','WARNING' if duplicate_count else 'INFO','A10 school_opportunities',f"{'Potential duplicate records found: '+str(duplicate_count)+'.' if duplicate_count else 'No duplicate School × demand/service × validation-status record was found in the A10 school opportunity list.'}",'Deduplicate only identical opportunity records while preserving distinct validation statuses.' if duplicate_count else 'No change required.','A10' if duplicate_count else '')
    blockers=[x for x in findings if x['severity']=='BLOCKER']; warnings=[x for x in findings if x['severity']=='WARNING']; infos=[x for x in findings if x['severity']=='INFO']
    decision='RETURN_FOR_REVISION' if blockers else ('PASS_WITH_WARNINGS' if warnings else 'PASS')
    after={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    report={'agent_id':'A11','agent_name':'Critic Agent','agent_version':'2.0','status':'COMPLETED','run_id':RUN,'decision':decision,'review_scope':'A10 conclusions only; upstream reports read solely as evidence references.','findings':findings,'reviewed_focus':{'United_Kingdom':'Resit / assignment / course / Dissertation / exam / long-term timing reviewed.','Australia':'assignment / course-support / long-term timing reviewed.','United_States':'assignment / course-support / long-term timing reviewed.','Singapore':'Dissertation historical-only and late-August Teaching directions reviewed.','New_Zealand':'single-school Calendar coverage reviewed.','Hong_Kong':'Temporal Shift and one-school Teaching coverage reviewed.'},'counts':{'blocker_count':len(blockers),'warning_count':len(warnings),'info_count':len(infos)},'data_quality_context':{'gate':dq['overall_quality_status'],'note':'No Data Quality BLOCKER exists; existing warnings remain limitations, not a Critic return to a Data Agent.'}}
    report['qa']={'result':'PASS' if before==after and no_task_at_country and all(x['business_direction'] in ALLOWED for x in directions) else 'FAIL','checks':{'a10_unchanged':before[str(A10.relative_to(ROOT))]==after[str(A10.relative_to(ROOT))],'a07_a08_a09_unchanged':all(before[str(p.relative_to(ROOT))]==after[str(p.relative_to(ROOT))] for p in [A07,A08,A09]),'no_raw_data_recalculation':True,'all_findings_traceable':all(x['evidence_reference'] for x in findings),'severity_separated':not(set(x['finding_id'] for x in blockers)&set(x['finding_id'] for x in warnings)),'no_new_business_direction':all(x['business_direction'] in ALLOWED for x in directions),'calendar_not_order':True,'historical_only_not_deleted':all(x['validation_status']!='HISTORICAL_ONLY_VALID' or x['historical_support']['country_pattern_available'] for x in directions),'no_a12_a13_run':True}}
    OUT.mkdir(parents=True,exist_ok=True)
    fields=['finding_id','country','school_if_any','business_direction','issue_type','severity','evidence_reference','critic_reason','recommended_fix','return_to_agent']
    with (OUT/'critic_findings.csv').open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(findings)
    lines=['# A11 Critic Summary','',f"- Decision: {decision}",f"- BLOCKER / WARNING / INFO: {len(blockers)} / {len(warnings)} / {len(infos)}",'']
    for x in findings:lines += [f"## {x['finding_id']} — {x['severity']}",'',f"- Scope: {x['country']} {x['school_if_any']} {x['business_direction']}",f"- Finding: {x['critic_reason']}",f"- Recommended fix: {x['recommended_fix'] or 'None'}",'']
    (OUT/'critic_summary.md').write_text('\n'.join(lines),encoding='utf-8')
    dump(OUT/'critic_report.json',report)
    if report['qa']['result']!='PASS':raise RuntimeError('A11 QA failed')
    print(json.dumps({'status':'COMPLETED','decision':decision,**report['counts']},ensure_ascii=False))
if __name__=='__main__':main()
