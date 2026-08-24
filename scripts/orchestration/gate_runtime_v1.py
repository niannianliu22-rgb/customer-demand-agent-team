#!/usr/bin/env python3
"""Structured current-run Gate contract; decisions never parse Agent stdout."""
from __future__ import annotations
import csv, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
VALID={'PASS','PASS_WITH_WARNINGS','FAIL','RETURN_FOR_REVISION','HUMAN_REVIEW_REQUIRED'}
GATES=['SOURCE_GATE','SCHEMA_GATE','STANDARDIZATION_GATE','DATA_QUALITY_GATE','CONTEXT_GATE','INSIGHT_GATE','CRITIC_GATE','FORECAST_GATE','ACTION_GATE']
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def result(run_root, gate_name, producer_agent, decision, artifact_refs, blockers=None, warnings=None, return_to_agent=None, extra=None):
    if gate_name not in GATES or decision not in VALID: raise ValueError('invalid gate result')
    run_root=Path(run_root); payload={'gate_name':gate_name,'run_id':run_root.name,'producer_agent':producer_agent,'decision':decision,'blockers':blockers or [],'warnings':warnings or [],'return_to_agent':return_to_agent,'artifact_refs':artifact_refs,'checked_at':datetime.now(timezone.utc).isoformat()}
    payload.update(extra or {}); payload['checksum']=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    out=run_root/'gates';out.mkdir(parents=True,exist_ok=True);(out/f'{gate_name}.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');return payload
def standardization_blockers(root, refs):
    """Validate A05's frozen, run-bound standardization contract without reinterpretation."""
    artifacts=root/'artifacts'; blockers=[]
    try:
        dataset=artifacts/'unified_dataset.csv'; task_path=artifacts/'task_type_standardization_v17_audit.json'; channel_path=artifacts/'channel_standardization_v1_audit.json'; cleaning_path=artifacts/'cleaning_log.json'
        with dataset.open(encoding='utf-8-sig',newline='') as h: reader=csv.DictReader(h); headers=list(reader.fieldnames or []); rows=list(reader)
        schema=json.loads((root/'snapshots/canonical_schema.json').read_text(encoding='utf-8')); expected=[item['name'] for item in schema['fields']]
        task=json.loads(task_path.read_text(encoding='utf-8')); channel=json.loads(channel_path.read_text(encoding='utf-8')); cleaning=json.loads(cleaning_path.read_text(encoding='utf-8')); rules_snapshot=(root/'snapshots/standardization_rules.yaml').read_text(encoding='utf-8')
        import yaml
        rules_version=str(yaml.safe_load(rules_snapshot)['rules_version'])
        checks={
          'canonical_schema': headers==expected,
          'records_present': bool(rows),
          'cleaning_lineage': cleaning.get('run_id')==root.name and str(cleaning.get('business_rules_version'))==rules_version,
          'task_audit': task.get('run_id')==root.name and task.get('producer_agent')=='A05' and task.get('result')=='PASS' and task.get('rule_version')=='17.0' and task.get('checksums',{}).get('standardized_dataset')==sha(dataset),
          'channel_audit': channel.get('run_id')==root.name and channel.get('producer_agent')=='A05' and channel.get('result')=='PASS' and channel.get('channel_rules_version')=='1.0' and channel.get('checksums',{}).get('standardized_dataset')==sha(dataset),
          'school_lineage': all(row.get('school_standardization_status') and row.get('school_rule_id') and row.get('school_rule_version') and row.get('school_standardization_status')!='UNSTANDARDIZED' for row in rows),
          'task_lineage': all(row.get('task_type_standardization_status') in {'STANDARDIZED','MULTI_TASK','EXCLUDED_BY_BUSINESS_RULE','UNKNOWN'} and row.get('task_type_rule_id') and row.get('task_type_rule_version')=='17.0' for row in rows),
          'channel_lineage': all(row.get('channel_standardization_status')=='STANDARDIZED' and row.get('channel_rule_id') and row.get('channel_rule_version')=='1.0' for row in rows),
          'date_lineage': all('consultation_date_original' in row and 'consultation_date' in row and 'ddl_original' in row and 'ddl' in row for row in rows),
        }
        blockers=[{'issue':'STANDARDIZATION_CONTRACT_CHECK_FAILED','check':name} for name, passed in checks.items() if not passed]
    except Exception as exc:
        blockers=[{'issue':'STANDARDIZATION_CONTRACT_EVALUATION_ERROR','detail':str(exc)}]
    return blockers
def data_quality_warning_state(root):
    report=json.loads((root/'quality'/'data_quality_gate_report.json').read_text(encoding='utf-8'))
    decision=report.get('decision')
    if decision not in {'PASS','PASS_WITH_WARNINGS'}: return decision, [], {'warning_count':report.get('warning_count',0),'warnings_propagated':False}
    with (root/'quality'/'data_quality_issues.csv').open(encoding='utf-8-sig',newline='') as handle:
        warnings=[row for row in csv.DictReader(handle) if row.get('severity')=='WARNING']
    ledger={'run_id':root.name,'producer_agent':'A02','source_agent':'A06','source_gate':'DATA_QUALITY_GATE','warning_count':len(warnings),'warnings':warnings,'propagation_status':'ACTIVE','consumer_agents':['A07','A08','A09','A10','A11','A12','A13'],'resolved_by':None,'created_at':datetime.now(timezone.utc).isoformat()}
    audit=root/'audit'; audit.mkdir(parents=True,exist_ok=True); (audit/'warning_ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
    return decision, [{'issue':'DATA_QUALITY_WARNINGS','warning_count':len(warnings),'ledger':'audit/warning_ledger.json'}] if warnings else [], {'warning_count':len(warnings),'warnings_propagated':True,'warning_ledger':'audit/warning_ledger.json'}
def evaluate_contract(run_root, gate_name, producer_agent, refs, decision='PASS', warnings=None, blockers=None, return_to_agent=None):
    root=Path(run_root); missing=[x for x in refs if not (root/x).exists()]
    if missing: decision='FAIL'; blockers=(blockers or [])+[{'issue':'MISSING_CURRENT_RUN_ARTIFACT','artifact_refs':missing}]
    if gate_name=='STANDARDIZATION_GATE' and not missing:
        deep_blockers=standardization_blockers(root,refs)
        if deep_blockers:
            decision='FAIL'; blockers=(blockers or [])+deep_blockers; return_to_agent='A05'
    extra={}
    if gate_name=='DATA_QUALITY_GATE' and not missing:
        decision, propagated_warnings, extra=data_quality_warning_state(root)
        warnings=(warnings or [])+propagated_warnings
    return result(root,gate_name,producer_agent,decision,refs,blockers,warnings,return_to_agent,extra)
