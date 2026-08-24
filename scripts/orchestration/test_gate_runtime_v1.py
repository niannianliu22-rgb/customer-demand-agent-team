#!/usr/bin/env python3
"""Contract smoke for all nine Gates; creates only disposable smoke-run gate files."""
from __future__ import annotations
import json, shutil
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts/orchestration'))
from gate_runtime_v1 import GATES, result
OUT=ROOT/'artifacts/runtime_execution_v1/gate_smoke_test_report.json'; RUN=ROOT/'runs/SMOKE-GATES-V1'
def main():
    if RUN.exists(): shutil.rmtree(RUN)
    records=[]
    for gate in GATES:
        records.append(result(RUN,gate,'SMOKE','PASS',['artifacts/smoke.json']))
        records.append(result(RUN,gate,'SMOKE','PASS_WITH_WARNINGS',['artifacts/smoke.json'],warnings=[{'issue':'warning'}]))
        records.append(result(RUN,gate,'SMOKE','FAIL',['artifacts/smoke.json'],blockers=[{'issue':'blocker'}]))
        if gate=='CRITIC_GATE':records.append(result(RUN,gate,'A11','RETURN_FOR_REVISION',['artifacts/critic/critic_report.json'],return_to_agent='A10'))
    checks={'gate_9_9':len({x['gate_name'] for x in records})==9,'current_run_path':all(x['run_id']=='SMOKE-GATES-V1' for x in records),'contract_fields':all({'gate_name','run_id','producer_agent','decision','blockers','warnings','return_to_agent','artifact_refs','checked_at','checksum'}<=set(x) for x in records),'pass_fail_warning_paths':all(any(x['decision']==d for x in records if x['gate_name']==g) for g in GATES for d in ['PASS','PASS_WITH_WARNINGS','FAIL']),'critic_return_path':any(x['gate_name']=='CRITIC_GATE' and x['return_to_agent']=='A10' for x in records)}
    report={'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'record_count':len(records)};OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()
