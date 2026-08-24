#!/usr/bin/env python3
"""Run only provider/adapter diagnostics; never dispatch business Agents."""
from __future__ import annotations
import argparse, hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/orchestration'))
from model_runtime_adapter_v1 import invoke, ModelInvocationError
from model_output_envelope_adapter_v1 import build_agent_model_output_envelope, EnvelopeValidationError

def now(): return datetime.now(timezone.utc).isoformat()
def sha(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()

def append_audit(run:Path, audit:dict, agent_id:str, group:str|None, input_checksum:str, artifact_ref:str|None, status:str):
    completed=audit['completed_at']; started=audit['started_at']
    record={**audit,'run_id':run.name,'agent_id':agent_id,'parallel_group_id':group,
            'input_checksum':input_checksum,'input_artifact_checksum':input_checksum,
            'output_checksum':audit.get('raw_output_checksum'),'output_artifact_checksum':None,
            'artifact_ref':artifact_ref,'duration_ms':int((datetime.fromisoformat(completed)-datetime.fromisoformat(started)).total_seconds()*1000),
            'status':status}
    with (run/'audit/model_call_audit.jsonl').open('a',encoding='utf-8') as h:h.write(json.dumps(record,ensure_ascii=False)+'\n')
    return record

def smoke_artifact(run:Path, call_id:str, agent_id:str, envelope:dict)->Path:
    target=run/'audit/adapter_writer_smoke'/call_id/('historical_demand/historical_demand_report.json' if agent_id=='A07' else 'academic_context/academic_context_report.json')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps({'smoke_only':True,'agent_id':agent_id,'envelope':envelope},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return target

def describe(provider:str)->str:
    return 'model_content JSON object (Codex --output-last-message); payload is that object' if provider=='codex_cli' else 'stdout JSON wrapper object; payload is JSON decoded from wrapper.result'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('run_id'); args=ap.parse_args()
    run=ROOT/'runs'/args.run_id
    snapshot=run/'snapshots/model_runtime_binding.yaml'; routing=yaml.safe_load((run/'snapshots/model_routing.yaml').read_text())['routes']
    if not snapshot.exists(): raise SystemExit('missing run binding snapshot')
    os.environ['CDAT_RUNTIME_BINDING_CONFIG']=str(snapshot)
    raw_dir=run/'audit/model_raw_outputs'; report={'run_id':args.run_id,'created_at':now(),'diagnostic_only':True,'calls':[]}
    cases=[('A07','strong_codex','TIER_2_STRONG_REASONING'),('A08','medium_claude_sonnet','TIER_1_MEDIUM')]
    for agent_id,alias,tier in cases:
        call_id=f'DIAG-{agent_id}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")}'
        prompt='Return only this business payload as JSON:\n{"result":"OK"}'
        input_checksum=hashlib.sha256(prompt.encode()).hexdigest()
        context={'run_id':args.run_id,'agent_id':agent_id,'parallel_group_id':None,'call_id':call_id}
        item={'agent_id':agent_id,'call_id':call_id,'provider_alias':alias,'raw_structure':None,'raw_response_persisted':False,'normalizer':'FAIL','envelope_builder':'FAIL','artifact_writer_smoke':'FAIL'}
        try:
            payload,audit=invoke(alias,prompt,ROOT/'schemas/model_business_payload_v1.json',raw_output_dir=raw_dir,call_context=context,timeout=300)
            item['raw_response_persisted']=bool(audit.get('raw_response_persisted'))
            item['raw_structure']=describe(audit['model_name'].split(':',1)[0])
            item['normalizer']='PASS'
            envelope=build_agent_model_output_envelope({'agent_id':agent_id,'model_tier':tier},payload)
            item['envelope_builder']='PASS'
            smoke=smoke_artifact(run,call_id,agent_id,envelope); item['artifact_writer_smoke']='PASS' if smoke.exists() else 'FAIL'; item['smoke_artifact']=str(smoke.relative_to(run))
            append_audit(run,audit,agent_id,None,input_checksum,item['smoke_artifact'],'COMPLETED')
            item['status']='PASS'
        except ModelInvocationError as exc:
            audit=exc.audit; item.update(status='FAIL',failure=str(exc),raw_response_persisted=bool(audit.get('raw_response_persisted')))
            append_audit(run,audit,agent_id,None,input_checksum,None,'FAILED')
        except EnvelopeValidationError as exc:
            item.update(status='FAIL',failure=str(exc))
            # Invocation succeeded; its raw evidence and audit remain valid.
            append_audit(run,audit,agent_id,None,input_checksum,None,'OUTPUT_SCHEMA_FAILED')
        report['calls'].append(item)
    report['result']='PASS' if all(x['status']=='PASS' for x in report['calls']) else 'FAIL'
    out=run/'audit/model_output_adapter_diagnostic_v1.json'; out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__': main()
