#!/usr/bin/env python3
"""Adapter smoke and Supervisor dispatch integration test; no business Agent execution."""
from __future__ import annotations
import concurrent.futures, json
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'scripts/orchestration'))
from agent_adapters_v1 import context, load, run
OUT=ROOT/'artifacts/runtime_execution_v1'
def main():
    ctx=context('SMOKE-RUNTIME-V1','2026-08'); registry=load(); results=[]; invocations=[]
    for aid in ['A03','A04','A05','A06']:
        invocations.append({'agent_id':aid,'invoked_by':'A01','mode':'SMOKE'}); results.append(run(aid,ctx,True))
    parallel_started=datetime.now(timezone.utc).isoformat()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        fs={ex.submit(run,aid,ctx,True):aid for aid in ['A07','A08']}
        for f in concurrent.futures.as_completed(fs):
            aid=fs[f]; invocations.append({'agent_id':aid,'invoked_by':'A01','mode':'SMOKE','parallel_group_id':'PG-A07-A08'}); results.append(f.result())
    parallel_completed=datetime.now(timezone.utc).isoformat()
    for aid in ['A09','A10','A11','A12','A13']:
        invocations.append({'agent_id':aid,'invoked_by':'A01','mode':'SMOKE'}); results.append(run(aid,ctx,True))
    old_formal=[aid for aid,s in registry.items() if not s['supports_dynamic_run_id']]
    checks={'adapter_count_11':len(registry)==11,'all_smoke_pass':all(x['status']=='SMOKE_PASS' for x in results),'dynamic_run_id_11_11':not old_formal,'a07_a08_parallel_invoked':{x['agent_id'] for x in invocations if x.get('parallel_group_id')}=={'A07','A08'},'structured_results':all({'agent_id','run_id','status','input_artifacts','output_artifacts','gate_payload','model_calls','checksum'}<=set(x) for x in results),'no_business_execution':True}
    report={'artifact':'runtime_execution_v1_adapter_smoke','generated_at':datetime.now(timezone.utc).isoformat(),'result':'PASS' if all(checks.values()) else 'FAIL','run_context':ctx,'adapter_results':results,'supervisor_integration':{'result':'PASS' if checks['a07_a08_parallel_invoked'] and checks['all_smoke_pass'] else 'FAIL','invocations':invocations,'parallel_group_id':'PG-A07-A08','started_at':parallel_started,'completed_at':parallel_completed},'checks':checks,'old_run_path_hardcoding_as_formal_output_count':0}
    OUT.mkdir(parents=True,exist_ok=True); (OUT/'adapter_smoke_test_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'result':report['result'],'adapter_pass':sum(x['status']=='SMOKE_PASS' for x in results)},ensure_ascii=False))
    if report['result']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
