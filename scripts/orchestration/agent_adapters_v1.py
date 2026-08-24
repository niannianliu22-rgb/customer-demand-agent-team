#!/usr/bin/env python3
"""Structured adapter contract. Smoke mode validates dynamic-run dispatch without business execution."""
from __future__ import annotations
import hashlib, json, os, subprocess, threading
from datetime import datetime, timezone
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2]
REG=ROOT/'config/orchestration/agent_dispatch_registry_v1.yaml'
_AUDIT_LOCK=threading.Lock()
def now(): return datetime.now(timezone.utc).isoformat()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(): return yaml.safe_load(REG.read_text())['agents']
def context(run_id,target_month):
    return {'run_id':run_id,'target_month':target_month,'run_root':str(ROOT/'runs'/run_id),'dataset_version':'unified_dataset.csv','schema_version':'1.5.0','frozen_rule_versions':str(ROOT/'knowledge/frozen_registry_v2.json'),'model_routing_version':'1.0','governance_version':'1.0','workflow_version':'2.1','forecast_as_of_date':datetime.now().date().isoformat()}
def _model_envelope(agent_id,ctx,spec,route):
    run=ROOT/'runs'/ctx['run_id']; refs=[]
    for rel in spec['required_inputs']:
        path=run/rel; refs.append({'path':rel,'checksum':sha(path) if path.is_file() else None})
    warning=run/'audit/warning_ledger.json'; warning_payload=json.loads(warning.read_text(encoding='utf-8')) if warning.exists() else {'warning_count':0,'propagation_status':'NONE'}
    envelope={'run_id':ctx['run_id'],'agent_id':agent_id,'task':route['llm_trigger'],'required_inputs':spec['required_inputs'],'input_artifact_refs':refs,'warning_refs':{'path':'audit/warning_ledger.json','warning_count':warning_payload['warning_count'],'warning_status':warning_payload['propagation_status']},'frozen_rule_refs':[str(x) for x in route['evidence_boundary']['allowed_input_artifacts'] if 'frozen' in str(x) or 'calendar' in str(x)],'expected_output_schema':route['structured_output_schema'],'output_contract':spec['expected_outputs']}
    encoded=json.dumps(envelope,ensure_ascii=False,sort_keys=True)
    return envelope, hashlib.sha256(encoded.encode()).hexdigest()
def _invoke_model(agent_id,ctx,spec,route):
    from model_runtime_adapter_v1 import invoke
    from model_output_envelope_adapter_v1 import build_agent_model_output_envelope
    envelope,input_checksum=_model_envelope(agent_id,ctx,spec,route)
    prompt=('Return only the required JSON envelope. You are an evidence-bound agent. Use only this supplied input envelope; do not access or infer unregistered evidence. Do not decide gates, workflow, return targets, or downstream dispatch. '\
            'Provide a concise evidence interpretation, disclose propagated warnings, and keep all numeric computation deterministic. INPUT_ENVELOPE='+json.dumps(envelope,ensure_ascii=False,separators=(',',':')))
    run=ROOT/'runs'/ctx['run_id']
    response,audit=invoke(route['primary_model'],prompt,ROOT/route['structured_output_schema'],raw_output_dir=run/'audit'/'model_raw_outputs',call_context={'run_id':ctx['run_id'],'agent_id':agent_id,'parallel_group_id':ctx.get('parallel_group_id')})
    try:
        response=build_agent_model_output_envelope({'agent_id':agent_id,'model_tier':route['model_tier']},response)
    except Exception as exc:
        audit.update({'status':'FAILED','invocation_status':'OUTPUT_SCHEMA_FAILED'})
        setattr(exc,'audit',audit)
        raise
    out=run/'audit'/'model_output_envelopes'/f'{agent_id}.json'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(response,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    audit.update({'run_id':ctx['run_id'],'agent_id':agent_id,'parallel_group_id':ctx.get('parallel_group_id'),'provider':audit['model_name'].split(':',1)[0],'concrete_model':audit['actual_model'],'configured_effort':audit['configured_effort'],'input_checksum':input_checksum,'exit_code':0,'artifact_ref':spec['expected_outputs'][0]})
    return audit,out
def _append_model_audit(run_id,audit,output_checksum,status):
    record={**audit,'output_checksum':output_checksum,'output_artifact_checksum':output_checksum,'input_artifact_checksum':audit['input_checksum'],'duration_ms':int((datetime.fromisoformat(audit['completed_at'])-datetime.fromisoformat(audit['started_at'])).total_seconds()*1000),'status':status}
    with _AUDIT_LOCK:
        with (ROOT/'runs'/run_id/'audit'/'model_call_audit.jsonl').open('a',encoding='utf-8') as h:h.write(json.dumps(record,ensure_ascii=False)+'\n')
def _append_model_failure_audit(run_id,agent_id,ctx,runtime,input_checksum,started_at,failure_class):
    """Persist a prompt-free invocation attempt even when the provider fails.

    A failed call is still an auditable runtime event; retaining it prevents a
    Supervisor stage from losing the reason that it was blocked.
    """
    completed_at=now()
    record={'run_id':run_id,'agent_id':agent_id,'parallel_group_id':ctx.get('parallel_group_id'),
            'provider':runtime['provider'],'concrete_model':runtime['concrete_model'],
            'configured_effort':runtime['reasoning_effort'],'actual_effort':None,
            'invocation_mode':runtime['invocation_mode'],'started_at':started_at,
            'completed_at':completed_at,
            'duration_ms':int((datetime.fromisoformat(completed_at)-datetime.fromisoformat(started_at)).total_seconds()*1000),
            'exit_code':None,'status':'FAILED','failure_class':failure_class,
            'input_checksum':input_checksum,'input_artifact_checksum':input_checksum,
            'output_checksum':None,'output_artifact_checksum':None,'artifact_ref':None,
            'model_name':f"{runtime['provider']}:{runtime['concrete_model']}",
            'configured_model':runtime['concrete_model'],'actual_model':None,
            'model_tier':runtime['tier'],'fallback_used':runtime['fallback_used']}
    with _AUDIT_LOCK:
        with (ROOT/'runs'/run_id/'audit'/'model_call_audit.jsonl').open('a',encoding='utf-8') as h:h.write(json.dumps(record,ensure_ascii=False)+'\n')
def run(agent_id,ctx,smoke=False):
    spec=load()[agent_id]; start=now(); entry=ROOT/spec['entrypoint']; result={'agent_id':agent_id,'run_id':ctx['run_id'],'started_at':start,'input_artifacts':spec['required_inputs'],'output_artifacts':spec['expected_outputs'],'warnings':[],'blockers':[],'gate_payload':{'gate_after':spec['gate_after']},'model_calls':[],'adapter':'standard_agent_adapter'}
    if smoke:
        result.update(status='SMOKE_PASS',completed_at=now(),checksum=sha(entry)); return result
    # Bind every LLM-capable Agent to a qualified CLI-login provider before
    # executing its implementation.  Current business scripts are deterministic
    # and therefore make no model call until they explicitly use invoke().
    route_path=ROOT/'runs'/ctx['run_id']/'snapshots/model_routing.yaml'; route=yaml.safe_load(route_path.read_text(encoding='utf-8'))['routes'][agent_id]
    model_audit=None; model_output=None
    if route['llm_enabled'] is True or agent_id in {'A07','A08'}:
        binding_snapshot=ROOT/'runs'/ctx['run_id']/'snapshots/model_runtime_binding.yaml'
        previous=os.environ.get('CDAT_RUNTIME_BINDING_CONFIG'); os.environ['CDAT_RUNTIME_BINDING_CONFIG']=str(binding_snapshot)
        from model_runtime_adapter_v1 import resolve_chain
        runtime=resolve_chain(route['primary_model'])
        if runtime['availability']!='AVAILABLE':
            result.update(status='BLOCKED',completed_at=now(),checksum=sha(entry),blockers=[{'issue':'NO_QUALIFIED_CLI_PROVIDER','return_to_agent':agent_id,'missing_requirements':runtime['missing_requirements']}])
            return result
        result['runtime_binding']={k:runtime[k] for k in ['model_alias','provider','runtime_model_name','tier','fallback_used']}
        invocation_started=now()
        _,input_checksum=_model_envelope(agent_id,ctx,spec,route)
        try: model_audit,model_output=_invoke_model(agent_id,ctx,spec,route)
        except Exception as exc:
            # Do not retain provider stdout/stderr or prompts in the audit.
            failed_audit=getattr(exc,'audit',None)
            if failed_audit:
                failed_audit.update({'run_id':ctx['run_id'],'agent_id':agent_id,'parallel_group_id':ctx.get('parallel_group_id'),'provider':runtime['provider'],'concrete_model':runtime['concrete_model'],'input_checksum':input_checksum,'artifact_ref':None})
                _append_model_audit(ctx['run_id'],failed_audit,None,'FAILED')
            else:
                _append_model_failure_audit(ctx['run_id'],agent_id,ctx,runtime,input_checksum,invocation_started,type(exc).__name__)
            result.update(status='BLOCKED',completed_at=now(),checksum=sha(entry),blockers=[{'issue':'CLI_MODEL_INVOCATION_FAILED','detail':str(exc),'return_to_agent':agent_id}]); return result
        finally:
            if previous is None: os.environ.pop('CDAT_RUNTIME_BINDING_CONFIG',None)
            else: os.environ['CDAT_RUNTIME_BINDING_CONFIG']=previous
    env={**os.environ,'CDAT_RUN_ID':ctx['run_id'],'CDAT_TARGET_MONTH':ctx['target_month'],'CDAT_AGENT_ID':agent_id,'CDAT_MODEL_OUTPUT_ENVELOPE':str(model_output or '')}
    if ctx.get('parallel_group_id'): env['CDAT_PARALLEL_GROUP_ID']=ctx['parallel_group_id']
    proc=subprocess.run(['python3',str(entry),ctx['run_id']],cwd=ROOT,env=env,text=True,capture_output=True)
    result.update(status='COMPLETED' if proc.returncode==0 else 'FAILED',completed_at=now(),stdout=proc.stdout[-2000:],stderr=proc.stderr[-2000:],checksum=sha(entry))
    if model_audit:
        output=ROOT/'runs'/ctx['run_id']/spec['expected_outputs'][0]; _append_model_audit(ctx['run_id'],model_audit,sha(output) if output.exists() else None,result['status']); result['model_calls']=[model_audit]
    if proc.returncode: result['blockers']=[{'issue':'ENTRYPOINT_FAILED','return_to_agent':agent_id}]
    return result
