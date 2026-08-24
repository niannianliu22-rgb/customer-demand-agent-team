#!/usr/bin/env python3
"""Read-only Data Quality Agent V1 and DATA_QUALITY_GATE V1."""
from __future__ import annotations

import csv, hashlib, json, os
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]; RUN_ID=os.environ['CDAT_RUN_ID']
ART=ROOT/f'runs/{RUN_ID}/artifacts'; QUALITY=ROOT/f'runs/{RUN_ID}/quality'
DATA=ART/'unified_dataset.csv'; SCHEMA=ROOT/'schemas/canonical_schema.json'
STD_GATE=ROOT/f'runs/{RUN_ID}/gates/STANDARDIZATION_GATE.json'
ARTIFACT_CONTRACT=ROOT/'config/orchestration/artifact_contract_v1.yaml'
def contract_path(name):
    contract=yaml.safe_load(ARTIFACT_CONTRACT.read_text(encoding='utf-8'))
    item=contract['artifacts'][name]
    if item['producer_agent']!='A05' or 'A06' not in item['consumer_agents'] or item['required_by']!='DATA_QUALITY_AGENT':
        raise RuntimeError(f'Invalid A05→A06 artifact contract for {name}')
    return ROOT/f"runs/{RUN_ID}"/item['path']
CLEAN=contract_path('cleaning_log')
TASK_AUDIT=contract_path('task_type_standardization_audit')
CHANNEL_AUDIT=contract_path('channel_standardization_audit')
TASK_RULE=ROOT/'config/dimensions/task_type/task_type_rules_frozen_v17.yaml'; CHANNEL_RULE=ROOT/'config/dimensions/channel/channel_rules_frozen_v1.yaml'; SCHOOL_RULE=ROOT/'config/data/school_aliases.yaml'; DATE_RULE=ROOT/'config/data/date_standardization_rules_v1_1.yaml'; DATE_HUMAN=ROOT/'config/data/date_human_review_round1.json'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def iso(v):
    try: date.fromisoformat(v);return True
    except ValueError:return False
def issue(items,severity,field,record_id,typ,raw,standardized,rule,impact,return_agent=''):
    items.append({'issue_id':f'DQ-V1-{len(items)+1:04d}','severity':severity,'field':field,'record_id':record_id,'issue_type':typ,'raw_value':raw,'standardized_value':standardized,'rule_reference':rule,'downstream_impact':impact,'recommended_return_agent':return_agent})
def main():
    inputs=[DATA,SCHEMA,STD_GATE,CLEAN,TASK_AUDIT,CHANNEL_AUDIT,TASK_RULE,CHANNEL_RULE,SCHOOL_RULE,DATE_RULE,DATE_HUMAN]
    before={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    data=rows(DATA); header=list(data[0]); schema=json.loads(SCHEMA.read_text(encoding='utf-8')); gate=json.loads(STD_GATE.read_text(encoding='utf-8')); clean=json.loads(CLEAN.read_text(encoding='utf-8')); task_audit=json.loads(TASK_AUDIT.read_text(encoding='utf-8')); channel_audit=json.loads(CHANNEL_AUDIT.read_text(encoding='utf-8')); human_dates=json.loads(DATE_HUMAN.read_text(encoding='utf-8'))['approved_decisions']
    issues=[]; ids=[f"{r['source_id']}:{r['source_row_id']}" for r in data]
    # Integrity
    duplicate_ids=[x for x,n in Counter(ids).items() if n>1]
    for x in duplicate_ids: issue(issues,'BLOCKER','record_id',x,'DUPLICATE_RECORD_ID','',x,'canonical_schema.json','Can duplicate Historical Demand evidence.','Data Standardization Agent')
    required=[f['name'] for f in schema['fields'] if f.get('required')]
    missing_required={f:sum(not r.get(f,'').strip() for r in data) for f in required}
    for f,n in missing_required.items():
        if n: issue(issues,'BLOCKER',f,'ALL_DATASET_ROWS','REQUIRED_FIELD_MISSING',str(n),'','canonical_schema.json','Breaks source lineage or record identity.','Data Standardization Agent')
    lineage=['source_id','source_file','source_sheet','source_row_id','year','department']
    lineage_missing=sum(any(not r[x].strip() for x in lineage) for r in data)
    # Required/core metrics
    core=['country','school','degree_level','task_type','channel','consultation_date','ddl','amount_cny']
    metrics={f:{'non_null_count':sum(bool(r.get(f,'').strip()) for r in data),'missing_count':sum(not r.get(f,'').strip() for r in data)} for f in core}
    for f in metrics: metrics[f]['missing_share']=round(metrics[f]['missing_count']/len(data),6)
    # School quality
    school_status=Counter(r['school_standardization_status'] for r in data); canonical_school=sum(r['school_standardization_status']=='STANDARDIZED' for r in data); school_ids=sum(bool(r['school_id']) for r in data)
    pending_school=[r for r in data if r['school_standardization_status']=='REVIEW_REQUIRED']
    for r in pending_school: issue(issues,'BLOCKER','school',f"{r['source_id']}:{r['source_row_id']}",'UNAPPROVED_SCHOOL_STATUS',r['school_original'],r['school'],'RULE-013','Can corrupt school/market conclusions.','Data Standardization Agent')
    for r in data:
        if r['country_school_conflict']=='COUNTRY_SCHOOL_CONFLICT': issue(issues,'WARNING','country_school_conflict',f"{r['source_id']}:{r['source_row_id']}",'COUNTRY_SCHOOL_CONFLICT',r['country_original'],r['country'],'RULE-013','May affect school-country market allocation; retain for scoped review.')
    if canonical_school and school_ids<canonical_school: issue(issues,'WARNING','school_id','ALL_CANONICAL_SCHOOL_ROWS','PARTIAL_SCHOOL_ID_COVERAGE',str(canonical_school-school_ids),str(school_ids),'canonical_schema.json v1.5.0','Limits stable school-key joins; school names remain standardized.')
    # Task type quality
    task_modes=Counter(r['task_type_mode'] for r in data); invalid_components=[]
    official=set(); lines=TASK_RULE.read_text(encoding='utf-8').splitlines(); a=lines.index('official_task_types:')+1; b=lines.index('aliases:'); official={x[2:] for x in lines[a:b] if x.startswith('- ')}
    for r in data:
        rid=f"{r['source_id']}:{r['source_row_id']}"
        try: comps=json.loads(r['task_type_components'])
        except Exception: comps=None
        valid_mode=(r['task_type_mode']=='MULTI_TASK' and isinstance(comps,list) and len(comps)>1) or (r['task_type_mode']!='MULTI_TASK' and isinstance(comps,list))
        if not valid_mode or (isinstance(comps,list) and any(x not in official for x in comps)):
            invalid_components.append(r); issue(issues,'BLOCKER','task_type_components',rid,'INVALID_TASK_TYPE_COMPONENTS',r['task_type_components'],r['task_type'],'task_type_rules_frozen_v17.yaml','Can corrupt demand categorization.','Data Standardization Agent')
        if r['task_type_mode']=='UNKNOWN': issue(issues,'WARNING','task_type',rid,'APPROVED_UNKNOWN_TASK_TYPE',r['task_type_original'],r['task_type'],'task_type_rules_frozen_v17.yaml','Excluded from precise task-level demand conclusions.')
    # Channel quality
    bad_channel=[r for r in data if r['channel_standardization_status']!='STANDARDIZED']
    for r in bad_channel: issue(issues,'BLOCKER','channel',f"{r['source_id']}:{r['source_row_id']}",'UNAPPROVED_CHANNEL_STATUS',r['channel_original'],r['channel'],'channel_rules_frozen_v1.yaml','Can corrupt optional channel analysis.','Data Standardization Agent')
    legal_blank=sum(r['channel_original']=='新客户' and not r['channel'] and r['channel_group']=='新客户' for r in data)
    customer_group_schema_present='customer_group' in header
    if not customer_group_schema_present: issue(issues,'INFO','customer_group','ALL_DATASET_ROWS','FIELD_NOT_DEFINED_BY_SCHEMA','','','canonical_schema.json','Customer-group consistency is not applicable to this dataset.')
    # Date quality
    date_counts=Counter(); multi=[]
    for r in data:
        rid=f"{r['source_id']}:{r['source_row_id']}"
        for f in ['consultation_date','ddl']:
            value=r[f].strip(); raw=r[f'{f}_original'].strip(); human=human_dates.get(f'{rid}:{f}',{}).get('decision')
            if value:
                if not iso(value): issue(issues,'BLOCKER',f,rid,'INVALID_ISO_DATE',raw,value,'date_standardization_rules','Invalid date corrupts timing analysis.','Data Standardization Agent'); date_counts['INVALID_DATE']+=1
                else: date_counts['VALID']+=1
            elif human=='INVALID_DATE': date_counts['INVALID_DATE']+=1; issue(issues,'WARNING',f,rid,'APPROVED_INVALID_DATE',raw,'','date_human_review_round1.json','Record excluded from date-dependent analysis only.')
            else: date_counts['VALID_MISSING']+=1
        if r['ddl_components']:
            parts=r['ddl_components'].split(';'); multi.append(r)
            if not all(iso(x) for x in parts) or r['ddl']!=min(parts): issue(issues,'BLOCKER','ddl_components',rid,'INVALID_MULTI_DDL_LINEAGE',r['ddl_original'],r['ddl_components'],'canonical_schema.json v1.4.0','Can corrupt deadline/lead-time consumers.','Data Standardization Agent')
            else: date_counts['MULTI_DDL']+=1
        if r['ddl'] and r['consultation_date'] and r['ddl']<r['consultation_date']:
            issue(issues,'WARNING','ddl',rid,'DDL_BEFORE_CONSULTATION',r['ddl_original'],r['ddl'],'historical_time_pattern_v1','Excluded from Lead Time only; does not invalidate historical demand.')
    # Amount quality
    amount_valid=amount_missing=amount_invalid=negative=zero=0; max_amount=None
    for r in data:
        rid=f"{r['source_id']}:{r['source_row_id']}"; v=r['amount_cny'].strip()
        if not v: amount_missing+=1; continue
        try: n=float(v); amount_valid+=1; max_amount=max(max_amount or n,n)
        except ValueError: amount_invalid+=1; issue(issues,'BLOCKER','amount_cny',rid,'INVALID_NUMERIC',r['amount_original'],v,'RULE-009; RULE-010','Can corrupt value/revenue analyses.','Data Standardization Agent'); continue
        if n<0: negative+=1; issue(issues,'WARNING','amount_cny',rid,'NEGATIVE_AMOUNT',r['amount_original'],v,'RULE-009; RULE-010','May affect revenue/value aggregation.')
        if n==0: zero+=1; issue(issues,'WARNING','amount_cny',rid,'ZERO_AMOUNT',r['amount_original'],v,'RULE-009; RULE-010','May affect revenue/value aggregation.')
    # Approved missing amount is a visible quality characteristic, not an error.
    if amount_missing: issue(issues,'WARNING','amount_cny','ALL_MISSING_AMOUNT_ROWS','VALID_MISSING_AMOUNT',str(amount_missing),'','RULE-009; RULE-010','Limits revenue/Operational Value coverage only.')
    # Gate / report
    blockers=[x for x in issues if x['severity']=='BLOCKER']; warnings=[x for x in issues if x['severity']=='WARNING']; infos=[x for x in issues if x['severity']=='INFO']
    status='FAIL' if blockers else ('PASS_WITH_WARNINGS' if warnings else 'PASS')
    report={'agent_name':'Data Quality Agent','agent_version':'1.0','run_id':RUN_ID,'dataset_version':'unified_dataset.csv','schema_version':schema['schema_version'],'standardization_gate_status':gate['decision'],'record_count':len(data),'integrity_metrics':{'record_id_unique':not duplicate_ids,'duplicate_record_ids':len(duplicate_ids),'source_lineage_complete_rows':len(data)-lineage_missing,'source_lineage_missing_rows':lineage_missing,'expected_output_rows_from_cleaning_log':sum(x['output_rows'] for x in clean['sources']),'actual_rows':len(data)},'required_field_metrics':metrics,'school_quality':{'canonical_school_rows':canonical_school,'school_id_rows':school_ids,'school_id_coverage_of_canonical':round(school_ids/canonical_school,6) if canonical_school else 0,'status_distribution':dict(school_status),'unapproved_rows':len(pending_school),'country_school_conflict_rows':sum(r['country_school_conflict']=='COUNTRY_SCHOOL_CONFLICT' for r in data)},'task_type_quality':{'mode_distribution':dict(task_modes),'frozen_audit_result':task_audit['result'],'unknown_rows':task_modes['UNKNOWN'],'invalid_component_rows':len(invalid_components)},'channel_quality':{'frozen_audit_result':channel_audit['result'],'channel_group_distribution':dict(Counter(r['channel_group'] for r in data)),'legal_blank_secondary_channel_rows':legal_blank,'unapproved_rows':len(bad_channel),'customer_group_consistency':'NOT_APPLICABLE_SCHEMA_FIELD_NOT_DEFINED'},'date_quality':{'classification_counts':dict(date_counts),'ddl_before_consultation_rows':sum(x['issue_type']=='DDL_BEFORE_CONSULTATION' for x in issues),'multi_ddl_rows':len(multi),'downstream_impact':'DDL missing/invalid and DDL-before-consultation affect Lead Time coverage only; consultation_date, task_type and school support the core Historical Demand analysis.'},'amount_quality':{'valid_count':amount_valid,'valid_missing_count':amount_missing,'invalid_numeric_count':amount_invalid,'negative_count':negative,'zero_count':zero,'maximum_amount_cny':max_amount,'downstream_impact':'Missing amount limits revenue/value analysis only; it does not prevent demand-count analysis.'},'cross_field_quality':{'school_country_conflicts':sum(r['country_school_conflict']=='COUNTRY_SCHOOL_CONFLICT' for r in data),'task_components_invalid':len(invalid_components),'customer_group_channel':'NOT_APPLICABLE_SCHEMA_FIELD_NOT_DEFINED','ddl_consultation_anomalies':sum(x['issue_type']=='DDL_BEFORE_CONSULTATION' for x in issues),'key_account_task_type':'NOT_APPLICABLE_SCHEMA_FIELD_NOT_DEFINED'},'blocker_count':len(blockers),'warning_count':len(warnings),'info_count':len(infos),'overall_quality_status':status,'agent_status':'RETURN_REQUIRED' if status=='FAIL' else 'COMPLETED','downstream_readiness':{'historical_demand_agent':status!='FAIL','academic_context_agent':status!='FAIL','field_effects':{'core_historical_demand':'consultation_date, task_type, school, and country are required for timing/category/market analysis; approved date exceptions are excluded only from date-dependent slices.','lead_time':'ddl VALID_MISSING, INVALID_DATE and DDL_BEFORE_CONSULTATION reduce Lead Time coverage only.','operational_value':'amount_cny VALID_MISSING limits value/revenue coverage only.'}},'qa':{'dataset_unchanged':before[str(DATA.relative_to(ROOT))]==sha(DATA),'frozen_rules_unchanged':all(before[str(p.relative_to(ROOT))]==sha(p) for p in [SCHEMA,TASK_RULE,CHANNEL_RULE,SCHOOL_RULE,DATE_RULE,DATE_HUMAN]),'standardization_gate_unchanged':before[str(STD_GATE.relative_to(ROOT))]==sha(STD_GATE),'all_blockers_traceable':all(x['record_id'] and x['rule_reference'] for x in blockers),'valid_missing_not_blocker':not any(x['severity']=='BLOCKER' and x['issue_type']=='VALID_MISSING_AMOUNT' for x in issues),'warnings_separate_from_blockers':not(set(x['issue_id'] for x in blockers)&set(x['issue_id'] for x in warnings))}}
    QUALITY.mkdir(exist_ok=True)
    (QUALITY/'quality_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    fields=['issue_id','severity','field','record_id','issue_type','raw_value','standardized_value','rule_reference','downstream_impact','recommended_return_agent']
    with (QUALITY/'data_quality_issues.csv').open('w',encoding='utf-8-sig',newline='') as h: w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(issues)
    returns=Counter(x['recommended_return_agent'] for x in blockers if x['recommended_return_agent'])
    gate_report={'gate_name':'DATA_QUALITY_GATE','gate_version':'1.0','run_id':RUN_ID,'required_artifacts':[str(DATA.relative_to(ROOT)),str(QUALITY/'quality_report.json'),str(STD_GATE.relative_to(ROOT))],'decision':status,'blocker_count':len(blockers),'warning_count':len(warnings),'return_to_agent':next(iter(returns)) if len(returns)==1 else (sorted(returns) if returns else None),'agent_status':report['agent_status'],'checked_at':datetime.now(timezone.utc).isoformat(),'qa':report['qa']}
    (QUALITY/'data_quality_gate_report.json').write_text(json.dumps(gate_report,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(report['qa'].values()): raise RuntimeError('Data Quality QA failed')
    print(json.dumps({'status':status,'records':len(data),'blockers':len(blockers),'warnings':len(warnings),'infos':len(infos),'agent_status':report['agent_status']},ensure_ascii=False))
if __name__=='__main__':main()
