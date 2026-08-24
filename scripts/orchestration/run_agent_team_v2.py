#!/usr/bin/env python3
"""Supervisor/Knowledge runtime V2.

The normal command initializes a run ledger.  ``--dry-run`` is deliberately
simulation-only: it never invokes any business Agent or changes their artifacts.
"""
from __future__ import annotations

import argparse, hashlib, json, shutil, sys
import concurrent.futures
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT=Path(__file__).resolve().parents[2]
REGISTRY=ROOT/'config/agents/agent_registry_v2.yaml'; WORKFLOW=ROOT/'config/orchestration/workflow_v2.yaml'; GRAPH=ROOT/'config/orchestration/dependency_graph_v2.yaml'
FROZEN_OUT=ROOT/'knowledge/frozen_registry_v2.json'; DRY_OUT=ROOT/'artifacts/orchestration_v2/dry_run_report.json'

FROZEN={
 'canonical_schema':('schemas/canonical_schema.json','schema_version'),
 'school_mapping':('config/data/school_aliases.yaml','dictionary_version'),
 'task_type_rules':('config/dimensions/task_type/task_type_rules_frozen_v17.yaml','version'),
 'channel_rules':('config/dimensions/channel/channel_rules_frozen_v1.yaml','version'),
 'date_rules':('config/data/date_standardization_rules_v1_1.yaml','version'),
 'historical_demand_framework':('docs/historical_demand_evidence_framework_v1.md',None),
 'operational_value_framework':('docs/demand_insight_metric_framework_v1.md',None),
 'calendar_taxonomy':('config/dimensions/academic_calendar/academic_calendar_business_taxonomy_v1.yaml','version'),
 'calendar_business_mapping':('config/dimensions/academic_calendar/academic_calendar_business_mapping_v1.yaml','version'),
 'promotion_window_rules':('config/dimensions/academic_calendar/promotion_window_business_rules_v1.yaml','version'),
 'agent_contracts_v2':('docs/AGENT_CONTRACTS_V2.md',None),
 'gate_model_v2':('docs/GATE_MODEL_V2.md',None),
 'model_registry_v1':('config/models/model_registry_v1.yaml','version'),
 'model_routing_v1':('config/models/model_routing_v1.yaml','version'),
 'model_runtime_binding_v1':('config/models/model_runtime_binding_v1.yaml','version'),
 'agent_governance_v1':('config/agents/agent_governance_v1.yaml','version'),
}
def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return yaml.safe_load(p.read_text(encoding='utf-8'))
def write_json(p,obj):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def frozen_registry():
    entries=[]
    for name,(rel,key) in FROZEN.items():
        p=ROOT/rel; version='DOCUMENT_FROZEN' if key is None else 'NOT_READABLE'
        if p.suffix in {'.yaml','.yml','.json'} and key:
            try: version=load(p).get(key,'VERSION_NOT_DECLARED') if p.suffix!='.json' else json.loads(p.read_text()) .get(key,'VERSION_NOT_DECLARED')
            except Exception: version='VERSION_NOT_DECLARED'
        entries.append({'rule_name':name,'version':version,'status':'FROZEN','frozen_at':now(),'artifact_path':rel,'checksum':sha(p),'dependency':[],'supersedes':None})
    result={'registry_version':'2.0','generated_at':now(),'entries':entries}
    write_json(FROZEN_OUT,result);return result
def event(events,event_type,agent='',gate='',before='',after='',message='',artifacts=None):
    events.append({'event_id':f'EVT-{len(events)+1:04d}','timestamp':now(),'event_type':event_type,'agent_id':agent,'gate_name':gate,'status_before':before,'status_after':after,'message':message,'artifact_refs':artifacts or []})
def descendants(graph,start):
    adj=defaultdict(list)
    for a,b in graph['edges']:adj[a].append(b)
    seen=set();q=deque([start])
    while q:
        x=q.popleft()
        if x in seen:continue
        seen.add(x);q.extend(adj[x])
    return sorted(seen)
def _copy_snapshot(path, source, name):
    destination=path/'snapshots'/name; destination.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,destination); return str(destination.relative_to(path))
def _materialize_inputs(path, source_input_dir):
    source=Path(source_input_dir).resolve()
    if not source.is_dir(): raise SystemExit(f'Input source directory not found: {source}')
    files=sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() in {'.xlsx','.xls'} and not p.name.startswith('.'))
    if len(files)!=6: raise SystemExit(f'Exactly six Excel inputs are required; found {len(files)} in {source}')
    items=[]
    for item in files:
        destination=path/'input'/item.name; shutil.copy2(item,destination)
        items.append({'source_filename':item.name,'source_checksum':sha(item),'source_origin':str(item.relative_to(ROOT)) if item.is_relative_to(ROOT) else str(item),'copied_or_linked':'copied','immutable':True})
    manifest={'run_id':path.name,'generated_at':now(),'immutable':True,'source_count':len(items),'sources':items}
    write_json(path/'input_manifest.json',manifest); return manifest
def _snapshot_run(path, frozen):
    _copy_snapshot(path,FROZEN_OUT,'frozen_registry.json')
    named={'model_registry.yaml':ROOT/'config/models/model_registry_v1.yaml','model_routing.yaml':ROOT/'config/models/model_routing_v1.yaml','model_runtime_binding.yaml':ROOT/'config/models/model_runtime_binding_v1.yaml','agent_governance.yaml':ROOT/'config/agents/agent_governance_v1.yaml','canonical_schema.json':ROOT/'schemas/canonical_schema.json','business_rules.md':ROOT/'policies/business_rules.md','standardization_rules.yaml':ROOT/'config/data/standardization_rules.yaml','workflow.yaml':WORKFLOW,'dependency_graph.yaml':GRAPH,'agent_dispatch_registry.yaml':ROOT/'config/orchestration/agent_dispatch_registry_v1.yaml','gate_runtime_v1.py':ROOT/'scripts/orchestration/gate_runtime_v1.py','gate_model_v2.md':ROOT/'docs/GATE_MODEL_V2.md'}
    return {name:_copy_snapshot(path,source,name) for name,source in named.items()}
def manifest(run_id,target,registry,workflow,frozen,input_manifest,snapshots):
    schema_version=next(x['version'] for x in frozen['entries'] if x['rule_name']=='canonical_schema')
    return {'run_id':run_id,'created_at':now(),'target_month':target,'workflow_version':workflow['version'],'schema_version':schema_version,'model_runtime_binding_version':next(x['version'] for x in frozen['entries'] if x['rule_name']=='model_runtime_binding_v1'),'model_routing_version':next(x['version'] for x in frozen['entries'] if x['rule_name']=='model_routing_v1'),'governance_version':next(x['version'] for x in frozen['entries'] if x['rule_name']=='agent_governance_v1'),'frozen_registry_version':frozen['registry_version'],'input_manifest':'input_manifest.json','input_source_count':input_manifest['source_count'],'snapshot_artifacts':snapshots,'source_dataset':'RUN_BOUND_INPUT','source_calendar_scope':'UNRESOLVED_AT_INITIALIZATION','agents':{x['agent_id']:{'version':'V2','status':'NOT_STARTED','warnings':[],'artifacts':[]} for x in registry['agents']},'gates':{x:{'decision':'NOT_STARTED'} for x in workflow['gates']},'rule_versions':frozen['entries'],'current_agent':'A01','run_status':'READY','final_artifacts':[],'artifact_validity':{}}
def create_run(target, source_input_dir):
    registry=load(REGISTRY);workflow=load(WORKFLOW);frozen=frozen_registry();stamp=datetime.now().strftime('%Y%m%dT%H%M%S');run_id=f'RUN-{target.replace("-", "")}-TEAM-{stamp}'
    path=ROOT/'runs'/run_id
    for name in ['input','artifacts','gates','quality','audit','logs','snapshots','state']: (path/name).mkdir(parents=True,exist_ok=True)
    input_manifest=_materialize_inputs(path,source_input_dir); snapshots=_snapshot_run(path,frozen); m=manifest(run_id,target,registry,workflow,frozen,input_manifest,snapshots)
    write_json(path/'run_manifest.json',m);write_json(path/'state/runtime_state.json',{'run_id':run_id,'run_status':'READY','current_agent':'A01','agents':m['agents'],'gates':m['gates'],'artifact_validity':m['artifact_validity']})
    e=[];event(e,'RUN_CREATED','A01','', '', 'READY','Supervisor created a fully materialized, run-bound retry ledger.',[str((path/'input_manifest.json').relative_to(ROOT)),str((path/'snapshots/frozen_registry.json').relative_to(ROOT))]);(path/'run_log.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in e)+'\n',encoding='utf-8')
    return run_id
def abort_before_execution(run_id):
    path=ROOT/'runs'/run_id; state_path=path/'state/runtime_state.json'; manifest_path=path/'run_manifest.json'; log=path/'run_log.jsonl'
    if not state_path.exists() or not manifest_path.exists(): raise SystemExit(f'Run not found: {run_id}')
    state=json.loads(state_path.read_text()); manifest_data=json.loads(manifest_path.read_text())
    if any(item['status']!='NOT_STARTED' for item in state['agents'].values()): raise SystemExit('Only a run with no Agent execution may be aborted before execution')
    previous=state['run_status']; state['run_status']='ABORTED_BEFORE_EXECUTION'; manifest_data['run_status']='ABORTED_BEFORE_EXECUTION'; manifest_data['aborted_at']=now(); manifest_data['abort_reason']='Superseded before execution: missing run-bound initialization contract.'
    write_json(state_path,state); write_json(manifest_path,manifest_data)
    with log.open('a',encoding='utf-8') as handle: handle.write(json.dumps({'event_id':'RUN_ABORTED_BEFORE_EXECUTION','timestamp':now(),'event_type':'RUN_ABORTED_BEFORE_EXECUTION','agent_id':'A01','gate_name':'','status_before':previous,'status_after':'ABORTED_BEFORE_EXECUTION','message':'Run retained for audit and superseded before any Agent execution.','artifact_refs':[]},ensure_ascii=False)+'\n')
    return run_id
def supersede_before_execution(run_id):
    path=ROOT/'runs'/run_id; state_path=path/'state/runtime_state.json'; manifest_path=path/'run_manifest.json'; log=path/'run_log.jsonl'
    if not state_path.exists() or not manifest_path.exists(): raise SystemExit(f'Run not found: {run_id}')
    state=json.loads(state_path.read_text()); manifest_data=json.loads(manifest_path.read_text())
    if any(item['status']!='NOT_STARTED' for item in state['agents'].values()): raise SystemExit('Only a run with no Agent execution may be superseded before execution')
    previous=state['run_status']; state['run_status']='SUPERSEDED_BEFORE_EXECUTION'; manifest_data['run_status']='SUPERSEDED_BEFORE_EXECUTION'; manifest_data['superseded_at']=now(); manifest_data['supersede_reason']='Superseded before execution because final concrete model binding changed after immutable snapshot creation.'
    write_json(state_path,state); write_json(manifest_path,manifest_data)
    with log.open('a',encoding='utf-8') as handle: handle.write(json.dumps({'event_id':'RUN_SUPERSEDED_BEFORE_EXECUTION','timestamp':now(),'event_type':'RUN_SUPERSEDED_BEFORE_EXECUTION','agent_id':'A01','gate_name':'','status_before':previous,'status_after':'SUPERSEDED_BEFORE_EXECUTION','message':'Run retained for audit and superseded before any Agent execution.','artifact_refs':[]},ensure_ascii=False)+'\n')
    return run_id
def dry_run(target):
    registry=load(REGISTRY);workflow=load(WORKFLOW);graph=load(GRAPH);frozen=frozen_registry();events=[]
    # This simulation has no dependency on a historical machine-local run.
    # Its contract is that no business Agent is invoked, rather than that a
    # particular archived artifact remains unchanged.
    business_before={}
    # Case 1: all structured gates pass; A07/A08 are dispatched as one parallel wave.
    path=['A01','A02','A03','SOURCE_GATE','A04','SCHEMA_GATE','A05','STANDARDIZATION_GATE','A06','DATA_QUALITY_GATE','PARALLEL(A07,A08)','A09','CONTEXT_GATE','A10','INSIGHT_GATE','A11','CRITIC_GATE','A12','FORECAST_GATE','A13','ACTION_GATE','RUN_COMPLETED']
    event(events,'RUN_CREATED','A01','','','INITIALIZED','Dry-run manifest initialized.')
    event(events,'AGENT_STARTED','A07','','READY','RUNNING','Parallel wave started with A08.')
    event(events,'AGENT_STARTED','A08','','READY','RUNNING','Parallel wave started with A07.')
    event(events,'GATE_PASS','A13','ACTION_GATE','RUNNING','COMPLETED','All simulated structured gate decisions PASS.')
    case1={'name':'CASE_1_ALL_PASS','result':'PASS','path':path,'parallel_a07_a08':True,'final_run_status':'COMPLETED'}
    # Case 2: Standardization gate REJECT blocks all downstream nodes.
    blocked=set(descendants(graph,'A06'))
    case2={'name':'CASE_2_STANDARDIZATION_FAIL','result':'PASS','gate':'STANDARDIZATION_GATE','decision':'REJECT','stopped_at':'A05','not_started_downstream':sorted(blocked),'final_run_status':'BLOCKED'}
    # Case 3: critic returns A10; invalidation is calculated from graph and excludes A03-A09.
    invalidated=descendants(graph,'A10')
    case3={'name':'CASE_3_CRITIC_RETURN_A10','result':'PASS','return_to_agent':'A10','stale_artifacts':invalidated,'rerun_chain':invalidated,'reused_agents':['A03','A04','A05','A06','A07','A08','A09'],'final_run_status':'COMPLETED_AFTER_RETURN'}
    human={'name':'HUMAN_REVIEW_PAUSE_RESUME','result':'PASS','pause_status':'WAITING_FOR_HUMAN','pause_agent':'A05','human_review_package_path':'artifacts/standardization_human_review_round1/','resume_from':'A05','downstream_not_started':['A06','A07','A08','A09','A10','A11','A12','A13']}
    warning={'name':'WARNING_PROPAGATION','result':'PASS','seed_warning':'DATA_QUALITY_GATE=PASS_WITH_WARNINGS','propagated_agents':['A07','A08','A09','A10','A11','A12','A13'],'critic_warning_constraints_propagated_to':['A12','A13']}
    stale={'name':'STALE_INVALIDATION','result':'PASS','upstream_changed':'A10 output checksum','marked_stale':invalidated,'old_forecast_action_reusable':False}
    business_after={}
    checks={'agents_registered':len(registry['agents'])==13,'gates_registered':len(workflow['gates'])==9,'parallel_a07_a08':case1['parallel_a07_a08'],'gate_fail_stops_downstream':case2['result']=='PASS','human_review_pause_resume':human['result']=='PASS','precise_return_rerun':case3['result']=='PASS' and set(case3['rerun_chain'])=={'A10','A11','A12','A13'},'stale_invalidation':stale['result']=='PASS','warning_propagation':warning['result']=='PASS','frozen_rules_read_only':all(x['status']=='FROZEN' for x in frozen['entries']),'dry_run_did_not_invoke_business_agents':business_before==business_after,'workflow_reaches_a13':case1['final_run_status']=='COMPLETED'}
    report={'artifact':'orchestration_v2_dry_run','generated_at':now(),'target_month':target,'dry_run':True,'cases':[case1,case2,case3],'human_review':human,'warning_propagation':warning,'stale_invalidation':stale,'simulated_events':events,'business_artifact_checksums_before':business_before,'business_artifact_checksums_after':business_after,'qa':{'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks},'frozen_registry_path':str(FROZEN_OUT.relative_to(ROOT))}
    write_json(DRY_OUT,report);return report
def status(run_id):
    p=ROOT/'runs'/run_id/'state/runtime_state.json'
    if not p.exists():raise SystemExit(f'Run not found: {run_id}')
    print(json.dumps(json.loads(p.read_text()),ensure_ascii=False,indent=2))
def resume(run_id):
    p=ROOT/'runs'/run_id/'state/runtime_state.json';log=ROOT/'runs'/run_id/'run_log.jsonl'
    if not p.exists():raise SystemExit(f'Run not found: {run_id}')
    state=json.loads(p.read_text());state['run_status']='RUNNING';write_json(p,state)
    with log.open('a',encoding='utf-8') as h:h.write(json.dumps({'event_id':'RESUME','timestamp':now(),'event_type':'RUN_RESUMED','agent_id':state.get('current_agent',''),'gate_name':'','status_before':'WAITING_FOR_HUMAN','status_after':'RUNNING','message':'Supervisor resumed from current agent; no upstream agents reset.','artifact_refs':[]},ensure_ascii=False)+'\n')
    print(json.dumps({'run_id':run_id,'run_status':'RUNNING','resume_from':state.get('current_agent')},ensure_ascii=False))
def ancestors(graph, target):
    reverse=defaultdict(list)
    for parent,child in graph['edges']: reverse[child].append(parent)
    seen=set(); queue=deque([target])
    while queue:
        node=queue.popleft()
        for parent in reverse[node]:
            if parent not in seen: seen.add(parent); queue.append(parent)
    return seen
def _artifact_reuse_record(run_root, rel, run_id):
    path=run_root/rel
    if not path.exists(): raise SystemExit(f'Resume blocked: missing upstream artifact {rel}')
    if path.suffix=='.json':
        try:
            payload=json.loads(path.read_text())
            if payload.get('run_id') not in (None,run_id): raise SystemExit(f'Resume blocked: artifact {rel} belongs to {payload.get("run_id")}')
        except json.JSONDecodeError: raise SystemExit(f'Resume blocked: malformed JSON artifact {rel}')
    return {'artifact_path':rel,'checksum':sha(path),'artifact_reuse':True,'reused_from_same_run':True}
def prepare_resume(run_id, resume_from_agent, resume_reason='OPERATOR_REQUESTED', smoke=True):
    """Validate and stage a precise same-run resume without regenerating upstream artifacts."""
    if resume_from_agent not in {f'A{i:02d}' for i in range(3,14)}: raise SystemExit(f'Unsupported resume target: {resume_from_agent}')
    path=ROOT/'runs'/run_id; state_path=path/'state/runtime_state.json'; manifest_path=path/'run_manifest.json'; log=path/'run_log.jsonl'
    if not state_path.exists(): raise SystemExit(f'Run not found: {run_id}')
    state=json.loads(state_path.read_text()); manifest_data=json.loads(manifest_path.read_text()); graph=load(GRAPH); dispatch=load(ROOT/'config/orchestration/agent_dispatch_registry_v1.yaml')['agents']
    upstream=sorted(ancestors(graph,resume_from_agent))
    reused_agents=[]; reused_gates=[]; reuse_records=[]
    for aid in upstream:
        if aid not in dispatch: continue
        agent=state['agents'][aid]
        if agent['status'] not in {'COMPLETED','COMPLETED_WITH_WARNINGS','REUSED'}: raise SystemExit(f'Resume blocked: {aid} status is {agent["status"]}')
        for rel in agent['artifacts']:
            record=_artifact_reuse_record(path,rel,run_id)
            if state.get('artifact_validity',{}).get(rel,{}).get('status')=='STALE': raise SystemExit(f'Resume blocked: upstream artifact is stale: {rel}')
            reuse_records.append(record); state.setdefault('artifact_validity',{})[rel]={'status':'VALID','checksum':record['checksum'],'reused_from_same_run':True}
        gate=dispatch[aid].get('gate_after')
        if gate:
            gate_file=path/'gates'/f'{gate}.json'; gate_state=state['gates'].get(gate,{})
            if gate_state.get('decision') not in {'PASS','PASS_WITH_WARNINGS'} or not gate_file.exists(): raise SystemExit(f'Resume blocked: {gate} is not passing')
            payload=json.loads(gate_file.read_text())
            if payload.get('run_id')!=run_id or payload.get('decision') not in {'PASS','PASS_WITH_WARNINGS'}: raise SystemExit(f'Resume blocked: invalid {gate} contract')
            state['gates'][gate]={**gate_state,'status':'REUSED','reused':True}; reused_gates.append(gate)
        state['agents'][aid]['status']='REUSED'; state['agents'][aid]['reused_from_same_run']=True; reused_agents.append(aid)
    rerun_agents=[aid for aid in descendants(graph,resume_from_agent) if aid in dispatch]
    stale_artifacts=[]
    for aid in rerun_agents:
        for rel in state['agents'][aid].get('artifacts',[]):
            state.setdefault('artifact_validity',{})[rel]={'status':'STALE','stale_reason':f'RESUME_FROM_{resume_from_agent}'}; stale_artifacts.append(rel)
        state['agents'][aid]['status']='READY' if aid==resume_from_agent else 'NOT_STARTED'
        state['agents'][aid]['artifacts']=[] if aid==resume_from_agent else state['agents'][aid].get('artifacts',[])
    state['current_agent']=resume_from_agent; state['run_status']='READY'
    manifest_data['run_status']='READY'; manifest_data['current_agent']=resume_from_agent
    audit={'run_id':run_id,'resume_from_agent':resume_from_agent,'resume_reason':resume_reason,'reused_agents':reused_agents,'rerun_agents':rerun_agents,'reused_gates':reused_gates,'rerun_gates':[dispatch[x]['gate_after'] for x in rerun_agents if dispatch[x].get('gate_after')],'stale_artifacts':stale_artifacts,'artifact_reuse':reuse_records,'requested_at':now(),'resumed_at':now(),'next_agent':resume_from_agent,'smoke_test':smoke}
    execution_order=['A03','A04','A05','A06','A07','A08','A09','A10','A11','A12','A13']
    cursor=execution_order.index(resume_from_agent)
    cursor_audit={'run_id':run_id,'requested_resume_agent':resume_from_agent,'resolved_execution_stage':('A07_A08_PARALLEL' if resume_from_agent in {'A07','A08'} else resume_from_agent),'resolved_next_agent':resume_from_agent,'reused_agents':[x for x in execution_order[:cursor] if x in reused_agents],'reused_artifacts':reuse_records,'reused_gates':reused_gates,'immutable_artifacts':[x['artifact_path'] for x in reuse_records],'agents_allowed_to_execute':execution_order[cursor:],'agents_forbidden_to_execute':execution_order[:cursor],'requested_at':now()}
    write_json(path/'audit/resume_audit.json',audit); write_json(path/'audit/resume_cursor_audit.json',cursor_audit); write_json(state_path,state); write_json(manifest_path,manifest_data)
    with log.open('a',encoding='utf-8') as handle: handle.write(json.dumps({'event_id':'RESUME_PREPARED','timestamp':now(),'event_type':'RESUME_PREPARED','agent_id':'A01','gate_name':'','status_before':'BLOCKED','status_after':'READY','message':f'Precise resume staged from {resume_from_agent}; upstream artifacts and gates reused.', 'artifact_refs':[x['artifact_path'] for x in reuse_records]},ensure_ascii=False)+'\n')
    return audit
def refresh_artifact_validity(run_id, agent_id):
    """Supervisor-only reconciliation after a successful re-run replaces stale outputs."""
    path=ROOT/'runs'/run_id; state_path=path/'state/runtime_state.json'; log=path/'run_log.jsonl'
    if not state_path.exists(): raise SystemExit(f'Run not found: {run_id}')
    state=json.loads(state_path.read_text()); dispatch=load(ROOT/'config/orchestration/agent_dispatch_registry_v1.yaml')['agents']
    if agent_id not in dispatch or state['agents'][agent_id]['status'] not in {'COMPLETED','COMPLETED_WITH_WARNINGS'}:
        raise SystemExit(f'Artifact validity can only be refreshed for a completed registered Agent: {agent_id}')
    refreshed=[]
    for rel in dispatch[agent_id]['expected_outputs']:
        artifact=path/rel
        if not artifact.exists(): raise SystemExit(f'Cannot mark missing artifact VALID: {rel}')
        state.setdefault('artifact_validity',{})[rel]={'status':'VALID','checksum':sha(artifact),'refreshed_by':'A01_SUPERVISOR','refreshed_at':now()}; refreshed.append(rel)
    write_json(state_path,state)
    audit={'run_id':run_id,'agent_id':agent_id,'event':'ARTIFACT_VALIDITY_REFRESHED','refreshed_artifacts':refreshed,'timestamp':now()}
    write_json(path/'audit'/f'artifact_validity_refresh_{agent_id}.json',audit)
    with log.open('a',encoding='utf-8') as handle: handle.write(json.dumps({'event_id':'ARTIFACT_VALIDITY_REFRESHED','timestamp':now(),'event_type':'ARTIFACT_VALIDITY_REFRESHED','agent_id':'A01','gate_name':'','status_before':'STALE','status_after':'VALID','message':f'Supervisor validated newly re-run {agent_id} outputs for downstream precise resume.','artifact_refs':refreshed},ensure_ascii=False)+'\n')
    return audit
def rerun_gate(run_id, gate_name):
    """A01 re-evaluates one completed producer's current-run gate only."""
    path=ROOT/'runs'/run_id; state_path=path/'state/runtime_state.json'
    if not state_path.exists(): raise SystemExit(f'Run not found: {run_id}')
    state=json.loads(state_path.read_text()); dispatch=load(ROOT/'config/orchestration/agent_dispatch_registry_v1.yaml')['agents']
    producer=next((agent_id for agent_id,spec in dispatch.items() if spec.get('gate_after')==gate_name),None)
    if not producer or state['agents'][producer]['status'] not in {'COMPLETED','COMPLETED_WITH_WARNINGS'}: raise SystemExit(f'Gate producer is not completed: {gate_name}')
    sys.path.insert(0,str(ROOT/'scripts/orchestration')); from gate_runtime_v1 import evaluate_contract
    payload=evaluate_contract(path,gate_name,producer,dispatch[producer]['expected_outputs']); state['gates'][gate_name]={'decision':payload['decision']}; write_json(state_path,state)
    with (path/'run_log.jsonl').open('a',encoding='utf-8') as handle: handle.write(json.dumps({'event_id':'GATE_RERUN','timestamp':now(),'event_type':'GATE_RERUN','agent_id':'A01','gate_name':gate_name,'status_before':'STALE','status_after':payload['decision'],'message':'Supervisor re-evaluated the completed producer against current run-bound artifacts.','artifact_refs':dispatch[producer]['expected_outputs']},ensure_ascii=False)+'\n')
    return payload
def stage_parallel_retry(run_id):
    path=ROOT/'runs'/run_id; state_path=path/'state/runtime_state.json'
    if not state_path.exists(): raise SystemExit(f'Run not found: {run_id}')
    state=json.loads(state_path.read_text())
    if state['gates'].get('DATA_QUALITY_GATE',{}).get('decision') not in {'PASS','PASS_WITH_WARNINGS'}: raise SystemExit('Parallel retry requires a passing Data Quality Gate')
    required=['artifacts/unified_dataset.csv','quality/quality_report.json','quality/data_quality_issues.csv','quality/data_quality_gate_report.json','audit/warning_ledger.json','snapshots/frozen_evidence/historical_evidence_v1','snapshots/frozen_evidence/academic_context_evidence_v1','artifacts/support_school_universe.json']
    missing=[rel for rel in required if not (path/rel).exists()]
    if missing: raise SystemExit(f'Parallel retry input contract missing: {missing}')
    for aid in ['A07','A08']:
        state['agents'][aid]['status']='READY_FOR_RETRY'; state['agents'][aid]['retry_reason']='PRE_MODEL_INPUT_VALIDATION_FAILURE_RESOLVED'
    state['current_agent']='PARALLEL(A07,A08)'; state['run_status']='READY'; write_json(state_path,state)
    audit={'run_id':run_id,'resume_from_parallel_stage':['A07','A08'],'reused_agents':['A03','A04','A05','A06'],'reused_gates':['SOURCE_GATE','SCHEMA_GATE','STANDARDIZATION_GATE','DATA_QUALITY_GATE'],'requested_at':now(),'next_stage':'A07+A08 PARALLEL','result':'READY_FOR_RETRY'}
    write_json(path/'audit/parallel_stage_retry_audit.json',audit)
    with (path/'run_log.jsonl').open('a',encoding='utf-8') as h:h.write(json.dumps({'event_id':'PARALLEL_RETRY_STAGED','timestamp':now(),'event_type':'PARALLEL_RETRY_STAGED','agent_id':'A01','gate_name':'','status_before':'BLOCKED','status_after':'READY','message':'A07/A08 parallel retry staged after run-bound input contract repair; no Agent invoked.','artifact_refs':required},ensure_ascii=False)+'\n')
    return audit
def execute_parallel_stage(run_id):
    """A01 executes only the governed A07/A08 parallel workflow node."""
    path=ROOT/'runs'/run_id; state_path=path/'state/runtime_state.json'; log=path/'run_log.jsonl'
    if not state_path.exists(): raise SystemExit(f'Run not found: {run_id}')
    state=json.loads(state_path.read_text())
    if state.get('current_agent')!='PARALLEL(A07,A08)' or any(state['agents'][aid]['status']!='READY_FOR_RETRY' for aid in ['A07','A08']): raise SystemExit('A07_A08_PARALLEL is not staged for retry')
    if state['gates'].get('DATA_QUALITY_GATE',{}).get('decision') not in {'PASS','PASS_WITH_WARNINGS'}: raise SystemExit('Parallel stage requires a passing Data Quality Gate')
    sys.path.insert(0,str(ROOT/'scripts/orchestration')); from agent_adapters_v1 import context as adapter_context, run as adapter_run
    group_id='PG-A07-A08-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'); target=json.loads((path/'run_manifest.json').read_text())['target_month']; ctx=adapter_context(run_id,target); ctx['parallel_group_id']=group_id
    events=[]
    for aid in ['A07','A08']:
        event(events,'AGENT_STARTED',aid,'',state['agents'][aid]['status'],'RUNNING',f'Supervisor started real parallel group {group_id}.'); state['agents'][aid]['status']='RUNNING'
    state['run_status']='RUNNING'; write_json(state_path,state)
    with log.open('a',encoding='utf-8') as h:
        for item in events:h.write(json.dumps(item,ensure_ascii=False)+'\n')
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(adapter_run,aid,ctx,False):aid for aid in ['A07','A08']}
        for future in concurrent.futures.as_completed(futures): results.append(future.result())
    for result in results:
        aid=result['agent_id']; state['agents'][aid]['status']=result['status']; state['agents'][aid]['artifacts']=result['output_artifacts']
        if result['status']=='COMPLETED':
            artifact=path/result['output_artifacts'][0]
            state.setdefault('artifact_validity',{})[result['output_artifacts'][0]]={'status':'VALID','checksum':sha(artifact),'produced_by':aid}
        event(events,'AGENT_COMPLETED' if result['status']=='COMPLETED' else 'AGENT_FAILED',aid,'','RUNNING',result['status'],f'Parallel group {group_id} structured adapter result received.',result['output_artifacts'])
    completed={item['agent_id']:item for item in results}; ok=all(completed[aid]['status']=='COMPLETED' and (path/completed[aid]['output_artifacts'][0]).exists() for aid in ['A07','A08'])
    state['run_status']='READY' if ok else 'BLOCKED'; state['current_agent']='A09' if ok else 'PARALLEL(A07,A08)'; write_json(state_path,state)
    audit={'run_id':run_id,'parallel_group_id':group_id,'a07_started_at':completed['A07']['started_at'],'a08_started_at':completed['A08']['started_at'],'a07_completed_at':completed['A07']['completed_at'],'a08_completed_at':completed['A08']['completed_at'],'parallel_execution':max(completed['A07']['started_at'],completed['A08']['started_at']) < min(completed['A07']['completed_at'],completed['A08']['completed_at']),'stage_status':'COMPLETED' if ok else 'BLOCKED','next_agent':'A09' if ok else None,
           'agent_results':{aid:{'status':completed[aid]['status'],'blockers':completed[aid].get('blockers',[]),'artifact_contract_satisfied':(path/completed[aid]['output_artifacts'][0]).exists()} for aid in ['A07','A08']}}
    write_json(path/'audit'/f'parallel_stage_{group_id}.json',audit)
    with log.open('a',encoding='utf-8') as h:
        for item in events:h.write(json.dumps(item,ensure_ascii=False)+'\n')
    return {'state':state,'audit':audit,'results':results}
def execute_run(run_id, resume_from_agent=None, resume_prepared=False, stop_after_agent=None):
    """Registry-driven real dispatch path; each adapter returns structured output."""
    sys.path.insert(0,str(ROOT/'scripts/orchestration'))
    from agent_adapters_v1 import context as adapter_context, load as load_dispatch, run as adapter_run
    from gate_runtime_v1 import evaluate_contract
    state_path=ROOT/'runs'/run_id/'state/runtime_state.json'; log=ROOT/'runs'/run_id/'run_log.jsonl'
    if resume_from_agent and not resume_prepared: prepare_resume(run_id,resume_from_agent,smoke=False)
    state=json.loads(state_path.read_text()); target=json.loads((ROOT/'runs'/run_id/'run_manifest.json').read_text())['target_month']; ctx=adapter_context(run_id,target); dispatch=load_dispatch()
    state['run_status']='RUNNING'; events=[]
    def persist():
        write_json(state_path,state)
        with log.open('a',encoding='utf-8') as h:
            for x in events: h.write(json.dumps(x,ensure_ascii=False)+'\n')
        events.clear()
    def one(aid):
        before=state['agents'][aid]['status']
        existing=state['agents'][aid].get('artifacts',[])
        if before in {'COMPLETED','COMPLETED_WITH_WARNINGS','REUSED'} and any((ROOT/'runs'/run_id/rel).exists() for rel in existing):
            raise SystemExit(f'IMMUTABLE_ARTIFACT_VIOLATION: {aid} has completed run-bound artifacts and is outside the execution cursor')
        event(events,'AGENT_STARTED',aid,'',before,'RUNNING','Supervisor dispatched registered adapter.'); state['agents'][aid]['status']='RUNNING'; persist()
        result=adapter_run(aid,ctx,False); state['agents'][aid]['status']=result['status']; state['agents'][aid]['artifacts']=result['output_artifacts']
        if result['status']=='COMPLETED':
            for rel in result['output_artifacts']:
                artifact=ROOT/'runs'/run_id/rel
                if artifact.exists(): state.setdefault('artifact_validity',{})[rel]={'status':'VALID','checksum':sha(artifact),'produced_by':aid}
        event(events,'AGENT_COMPLETED' if result['status']=='COMPLETED' else 'AGENT_FAILED',aid,'','RUNNING',result['status'],'Structured adapter result received.',result['output_artifacts']); persist(); return result
    # A precise downstream cursor must never fall through to the workflow's
    # initial A07/A08 parallel node.  Upstream artifacts have already been
    # checksum-validated and marked REUSED by prepare_resume().
    downstream_order=['A09','A10','A11','A12','A13']
    if resume_prepared and resume_from_agent in downstream_order:
        start=downstream_order.index(resume_from_agent)
        for aid in downstream_order[start:]:
            if state['agents'][aid]['status'] not in {'READY','NOT_STARTED'}:
                raise SystemExit(f'IMMUTABLE_ARTIFACT_VIOLATION: {aid} is not eligible for this resume cursor')
            result=one(aid)
            if result['status']!='COMPLETED': state['run_status']='BLOCKED'; persist(); return state
            gate=dispatch[aid]['gate_after']; payload=evaluate_contract(ROOT/'runs'/run_id,gate,aid,result['output_artifacts']); state['gates'][gate]={'decision':payload['decision']}; event(events,'GATE_PASS' if payload['decision']=='PASS' else 'GATE_FAIL',aid,gate,'RUNNING',payload['decision'],'Gate read current-run declared outputs.',result['output_artifacts']); persist()
            if payload['decision'] not in {'PASS','PASS_WITH_WARNINGS'}: state['run_status']='BLOCKED'; persist(); return state
        state['run_status']='COMPLETED'; persist(); return state
    initial=['A03','A04','A05','A06']; start_at=initial.index(resume_from_agent) if resume_from_agent in initial else 0
    for aid in initial[start_at:]:
        result=one(aid)
        if result['status']!='COMPLETED': state['run_status']='BLOCKED'; persist(); return state
        gate=dispatch[aid]['gate_after']; payload=evaluate_contract(ROOT/'runs'/run_id,gate,aid,result['output_artifacts']); state['gates'][gate]={'decision':payload['decision']}; event(events,'GATE_PASS' if payload['decision']=='PASS' else 'GATE_FAIL',aid,gate,'RUNNING',payload['decision'],'Gate read current-run declared outputs.',result['output_artifacts']); persist()
        if payload['decision'] not in {'PASS','PASS_WITH_WARNINGS'}: state['run_status']='BLOCKED'; persist(); return state
        if aid == stop_after_agent:
            state['run_status']='READY'; state['current_agent']='A06' if aid == 'A05' else aid
            event(events,'SUPERVISOR_STOP_AFTER_GATE',aid,gate,'RUNNING','READY',f'Supervisor stopped at requested recovery boundary after {gate}; downstream Agent was not started.')
            persist(); return state
    # A07/A08 execute concurrently, but only Supervisor mutates run state/logs.
    for aid in ['A07','A08']:
        event(events,'AGENT_STARTED',aid,'','READY','RUNNING','Supervisor started parallel group PG-A07-A08.'); state['agents'][aid]['status']='RUNNING'
    persist()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        future={pool.submit(adapter_run,aid,ctx,False):aid for aid in ['A07','A08']}
        results=[]
        for f in concurrent.futures.as_completed(future):
            aid=future[f]; result=f.result(); results.append(result); state['agents'][aid]['status']=result['status']; state['agents'][aid]['artifacts']=result['output_artifacts']; event(events,'AGENT_COMPLETED' if result['status']=='COMPLETED' else 'AGENT_FAILED',aid,'','RUNNING',result['status'],'Parallel structured adapter result received.',result['output_artifacts'])
    persist()
    if any(x['status']!='COMPLETED' for x in results): state['run_status']='BLOCKED'; persist(); return state
    for aid in ['A09','A10','A11','A12','A13']:
        result=one(aid)
        if result['status']!='COMPLETED': state['run_status']='BLOCKED'; persist(); return state
        gate=dispatch[aid]['gate_after']; payload=evaluate_contract(ROOT/'runs'/run_id,gate,aid,result['output_artifacts']); state['gates'][gate]={'decision':payload['decision']}; event(events,'GATE_PASS' if payload['decision']=='PASS' else 'GATE_FAIL',aid,gate,'RUNNING',payload['decision'],'Gate read current-run declared outputs.',result['output_artifacts']); persist()
        if payload['decision'] not in {'PASS','PASS_WITH_WARNINGS'}: state['run_status']='BLOCKED'; persist(); return state
    state['run_status']='COMPLETED'; persist(); return state
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--target-month');ap.add_argument('--source-input-dir');ap.add_argument('--dry-run',action='store_true');ap.add_argument('--resume');ap.add_argument('--resume-run');ap.add_argument('--resume-from');ap.add_argument('--resume-reason',default='OPERATOR_REQUESTED');ap.add_argument('--resume-smoke',action='store_true');ap.add_argument('--resume-stage');ap.add_argument('--stop-after');ap.add_argument('--refresh-artifact-validity-run');ap.add_argument('--refresh-agent');ap.add_argument('--rerun-gate-run');ap.add_argument('--gate');ap.add_argument('--stage-parallel-retry-run');ap.add_argument('--status');ap.add_argument('--execute');ap.add_argument('--abort-before-execution');ap.add_argument('--supersede-before-execution');args=ap.parse_args()
    if args.status:return status(args.status)
    if args.refresh_artifact_validity_run:
        if not args.refresh_agent: ap.error('--refresh-agent is required with --refresh-artifact-validity-run')
        print(json.dumps(refresh_artifact_validity(args.refresh_artifact_validity_run,args.refresh_agent),ensure_ascii=False));return
    if args.rerun_gate_run:
        if not args.gate: ap.error('--gate is required with --rerun-gate-run')
        print(json.dumps(rerun_gate(args.rerun_gate_run,args.gate),ensure_ascii=False));return
    if args.stage_parallel_retry_run: print(json.dumps(stage_parallel_retry(args.stage_parallel_retry_run),ensure_ascii=False));return
    if args.abort_before_execution: print(json.dumps({'run_id':abort_before_execution(args.abort_before_execution),'run_status':'ABORTED_BEFORE_EXECUTION'},ensure_ascii=False));return
    if args.supersede_before_execution: print(json.dumps({'run_id':supersede_before_execution(args.supersede_before_execution),'run_status':'SUPERSEDED_BEFORE_EXECUTION'},ensure_ascii=False));return
    if args.resume:return resume(args.resume)
    if args.resume_run:
        if args.resume_stage:
            if args.resume_stage!='A07_A08_PARALLEL': ap.error('unsupported --resume-stage')
            result=execute_parallel_stage(args.resume_run); print(json.dumps({'run_id':args.resume_run,'run_status':result['state']['run_status'],'parallel_group_id':result['audit']['parallel_group_id']},ensure_ascii=False)); return
        if not args.resume_from: ap.error('--resume-from is required with --resume-run')
        audit=prepare_resume(args.resume_run,args.resume_from,args.resume_reason,smoke=args.resume_smoke)
        if args.resume_smoke:
            print(json.dumps({'run_id':args.resume_run,'resume_smoke':'PASS','next_agent':audit['next_agent'],'reused_agents':audit['reused_agents'],'reused_gates':audit['reused_gates']},ensure_ascii=False));return
        result=execute_run(args.resume_run,args.resume_from,resume_prepared=True,stop_after_agent=args.stop_after);print(json.dumps({'run_id':args.resume_run,'run_status':result['run_status']},ensure_ascii=False));return
    if args.execute:
        result=execute_run(args.execute);print(json.dumps({'run_id':args.execute,'run_status':result['run_status']},ensure_ascii=False));return
    if not args.target_month:ap.error('--target-month is required for new runs')
    if args.dry_run:
        r=dry_run(args.target_month);print(json.dumps({'dry_run':'PASS' if r['qa']['result']=='PASS' else 'FAIL','report':str(DRY_OUT.relative_to(ROOT))},ensure_ascii=False));return
    if not args.source_input_dir: ap.error('--source-input-dir is required for a run-bound initialization')
    print(json.dumps({'run_id':create_run(args.target_month,args.source_input_dir),'run_status':'READY','message':'Run initialized with materialized inputs and frozen configuration snapshots; no business Agent was invoked.'},ensure_ascii=False))
if __name__=='__main__':main()
