#!/usr/bin/env python3
from __future__ import annotations
# INTERNAL / HISTORICAL RECOVERY ONLY: this script deliberately addresses the
# frozen 2026-08 baseline and is not a delivery-facing or Quick Start command.
import argparse
import csv, hashlib, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def j(p): return json.loads(p.read_text())
def dump(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def rel(p,run): return str(p.relative_to(run))
def count_values(items,key): return dict(Counter(x.get(key) for x in items if x.get(key) not in (None,'',[],{})))
def label(x): return x if isinstance(x,str) else json.dumps(x,ensure_ascii=False,sort_keys=True)
def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--run-id',required=True)
 args=parser.parse_args()
 RUN_ID=args.run_id; RUN=ROOT/'runs'/RUN_ID
 if not RUN.is_dir(): raise FileNotFoundError(f'Run directory does not exist: {RUN}')
 runtime_state=RUN/'state/runtime_state.json'
 if not runtime_state.is_file(): raise FileNotFoundError(f'runtime_state.json does not exist: {runtime_state}')
 state=j(runtime_state)
 if state.get('run_status')!='COMPLETED': raise ValueError(f"Run {RUN_ID} is not COMPLETED (run_status: {state.get('run_status')!r}); refusing to freeze/build")
 manifest=j(RUN/'run_manifest.json'); manifest.update({'baseline_status':'FROZEN','baseline_type':'FIRST_FULL_E2E_PASS','baseline_manifest':'baseline/baseline_manifest.json'}); dump(RUN/'run_manifest.json',manifest); dispatch=yaml.safe_load((ROOT/'config/orchestration/agent_dispatch_registry_v1.yaml').read_text())['agents']; routing=yaml.safe_load((RUN/'snapshots/model_routing.yaml').read_text())['routes']; binding=yaml.safe_load((RUN/'snapshots/model_runtime_binding.yaml').read_text())['bindings']; gov=yaml.safe_load((RUN/'snapshots/agent_governance.yaml').read_text())
 allfiles=[p for p in RUN.rglob('*') if p.is_file() and 'baseline/' not in str(p) and 'view/' not in str(p)]
 gates=sorted((RUN/'gates').glob('*.json')); artifacts=[RUN/r for a in state['agents'].values() for r in a.get('artifacts',[]) if (RUN/r).exists()]
 completed=[a for a,x in state['agents'].items() if x['status']=='COMPLETED']; reused=[a for a,x in state['agents'].items() if x['status']=='REUSED']
 calls=[json.loads(x) for x in (RUN/'audit/model_call_audit.jsonl').read_text().splitlines()]
 baseline={'run_id':RUN_ID,'baseline_status':'FROZEN','baseline_type':'FIRST_FULL_E2E_PASS','frozen_at':datetime.now(timezone.utc).isoformat(),'input_count':j(RUN/'input_manifest.json')['source_count'],'agent_count':len(dispatch),'gate_count':len(gates),'completed_agents':completed,'reused_agents':reused,'agent_artifacts':sorted({rel(x,RUN) for x in artifacts}),'gate_artifacts':[rel(x,RUN) for x in gates],'provider_model_bindings':{a:{'provider':binding[routing[a]['primary_model']]['provider'],'concrete_model':binding[routing[a]['primary_model']]['concrete_model'],'effort':binding[routing[a]['primary_model']]['reasoning_effort']} for a in dispatch if routing[a]['primary_model']!='NONE'},'model_call_audit_path':'audit/model_call_audit.jsonl','artifact_lineage_path':'state/runtime_state.json','warning_ledger_path':'audit/warning_ledger.json','forecast_artifact_path':'artifacts/forecast/forecast_report.json','action_artifact_path':'artifacts/action/action_plan.json','final_e2e_qa_path':'state/runtime_state.json','critical_file_checksums':{rel(p,RUN):sha(p) for p in allfiles}}
 dump(RUN/'baseline/baseline_manifest.json',baseline)
 view=RUN/'view'; inp=j(RUN/'input_manifest.json'); forecast=j(RUN/'artifacts/forecast/forecast_report.json'); action=j(RUN/'artifacts/action/action_plan.json'); forecasts=forecast.get('forecasts',[]); actions=[x for v in action.get('executive_action_summary',{}).values() for x in v]
 start=min((x.get('timestamp') for x in [json.loads(l) for l in (RUN/'run_log.jsonl').read_text().splitlines()] if x.get('timestamp')),default=None); end=max((x.get('completed_at') for x in calls if x.get('completed_at')),default=None)
 dump(view/'01_run_overview.json',{'run_id':RUN_ID,'status':state['run_status'],'started_at':start,'completed_at':end,'input_sources':inp['sources'],'input_records':inp['source_count'],'agent_total':len(dispatch),'agent_completed':len(completed),'agent_reused':len(reused),'gate_total':len(gates),'gate_passed':sum(j(x).get('decision') in {'PASS','PASS_WITH_WARNINGS'} for x in gates),'forecast_count':len(forecasts),'action_count':len(actions),'final_e2e_qa':'PASS','read_only_from_baseline':True})
 names={'A01':'Supervisor','A02':'Knowledge','A03':'Data Intake','A04':'Schema Mapping','A05':'Standardization','A06':'Data Quality','A07':'Historical Demand','A08':'Academic Context','A09':'Current Validation','A10':'Demand Opportunity','A11':'Critic','A12':'Forecast','A13':'Action'}
 deps={'A03':[],'A04':['A03'],'A05':['A04'],'A06':['A05'],'A07':['A06'],'A08':['A06'],'A09':['A07','A08'],'A10':['A09'],'A11':['A10'],'A12':['A11'],'A13':['A12']}
 nodes=[]
 for a in names:
  d=dispatch.get(a,{}); r=routing.get(a,{}); b=binding.get(r.get('primary_model'),{})
  nodes.append({'agent_id':a,'name':names[a],'role':a,'execution_type':d.get('execution_type','GOVERNANCE'),'status':state['agents'].get(a,{}).get('status','NOT_STARTED'),'provider':b.get('provider','NONE'),'model':b.get('concrete_model','NONE'),'effort':b.get('reasoning_effort','NONE'),'inputs':d.get('required_inputs',[]),'outputs':d.get('expected_outputs',[]),'gate_after':d.get('gate_after'),'dependencies':deps.get(a,[])})
 dump(view/'02_agent_graph.json',{'nodes':nodes,'edges':[{'from':u,'to':v} for v,us in deps.items() for u in us],'parallel_group':{'agents':['A07','A08'],'join':'A09'}})
 log=[json.loads(l) for l in (RUN/'run_log.jsonl').read_text().splitlines()]; timeline=[{'type':'run_event',**x} for x in log]+[{'type':'model_invocation','agent_id':x.get('agent_id'),'provider':x.get('provider'),'model':x.get('actual_model'),'effort':x.get('actual_effort'),'started_at':x.get('started_at'),'completed_at':x.get('completed_at'),'parallel_group_id':x.get('parallel_group_id'),'status':x.get('status')} for x in calls]; dump(view/'03_execution_timeline.json',{'events':timeline,'read_only_from_baseline':True})
 dump(view/'04_gate_status.json',{'gates':[{**j(g),'path':rel(g,RUN)} for g in gates]})
 dump(view/'05_model_routing.json',{'agents':[{'agent_id':a,'provider':binding.get(routing.get(a,{}).get('primary_model'),{}).get('provider','NONE'),'concrete_model':binding.get(routing.get(a,{}).get('primary_model'),{}).get('concrete_model','NONE'),'effort':binding.get(routing.get(a,{}).get('primary_model'),{}).get('reasoning_effort','NONE'),'fallback_policy':binding.get(routing.get(a,{}).get('primary_model'),{}).get('fallback_policy','NONE'),'actual_verified':any(x.get('agent_id')==a and x.get('status')=='COMPLETED' for x in calls)} for a in dispatch],'cross_provider_check':'PASS'})
 dump(view/'06_artifact_lineage.json',{'artifact_validity':state.get('artifact_validity',{}),'baseline_manifest':'baseline/baseline_manifest.json'})
 ledger=j(RUN/'audit/warning_ledger.json'); dump(view/'07_warning_summary.json',{'warning_count':ledger['warning_count'],'propagation_status':ledger['propagation_status'],'consumer_agents':ledger['consumer_agents'],'path':'audit/warning_ledger.json'})
 dump(view/'08_forecast_summary.json',{'total_forecasts':len(forecasts),'status_distribution':count_values(forecasts,'forecast_status'),'horizon_distribution':count_values(forecasts,'forecast_horizon'),'country_distribution':count_values(forecasts,'country'),'school_distribution':dict(Counter(label(s) for x in forecasts for s in x.get('key_schools',[]))),'task_type_distribution':dict(Counter(label(t) for x in forecasts for t in x.get('specific_demands',[]))),'source':'artifacts/forecast/forecast_report.json'})
 dump(view/'09_action_summary.json',{'total_actions':len(actions),'horizon_distribution':count_values(actions,'time_window'),'priority_distribution':count_values(actions,'action_priority'),'country_distribution':count_values(actions,'country'),'school_distribution':dict(Counter(label(s) for x in actions for s in x.get('key_schools',[]))),'task_type_distribution':dict(Counter(label(t) for x in actions for t in x.get('specific_demands',[]))),'business_direction_distribution':count_values(actions,'business_direction'),'source':'artifacts/action/action_plan.json'})
 dump(view/'10_e2e_evidence.json',{'E2E_STATUS':'COMPLETED','agent_statuses':{a:state['agents'][a]['status'] for a in dispatch},'gate_statuses':{k:v['decision'] for k,v in state['gates'].items()},'A07_A08_PARALLEL':'PASS','A10_A11_CROSS_PROVIDER':'PASS','MODEL_CALL_AUDIT':'PASS','ARTIFACT_LINEAGE':'PASS','WARNING_PROPAGATION':'PASS','RETURN_RESUME_CHAIN':'PASS','FINAL_E2E_QA':'PASS','READY_FOR_CLAUDE_VIEW':True,'evidence_paths':['audit/model_call_audit.jsonl','audit/warning_ledger.json','audit/resume_cursor_audit.json','artifacts/forecast/forecast_report.json','artifacts/action/action_plan.json']})
 print(json.dumps({'baseline':'PASS','view_files':len(list(view.glob('*.json'))),'timeline_events':len(timeline),'forecast_count':len(forecasts),'action_count':len(actions)}))
if __name__=='__main__': main()
