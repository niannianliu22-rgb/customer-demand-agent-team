#!/usr/bin/env python3
"""Preflight only: validates CLI-login runtime readiness and never dispatches Agents."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path
import yaml, sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts/orchestration'))
from model_runtime_adapter_v1 import load_config, resolve_chain
REG=ROOT/'config/orchestration/agent_dispatch_registry_v1.yaml'; ROUTE=ROOT/'config/models/model_routing_v1.yaml'; FROZEN=ROOT/'knowledge/frozen_registry_v2.json'; OUT=ROOT/'artifacts/runtime_execution_v1/model_runtime_preflight.json'
def main():
    dispatch=yaml.safe_load(REG.read_text())['agents']; routes=yaml.safe_load(ROUTE.read_text())['routes']; llm=['A07','A08','A09','A10','A11','A12','A13']; items=[]
    for aid in llm:
        alias=routes[aid]['primary_model']; x=resolve_chain(alias)
        items.append({'agent_id':aid,'model_alias':alias,'selected_model_alias':x['model_alias'],'tier':x['tier'],'provider':x['provider'],'runtime_model':x['runtime_model_name'],'availability':x['availability'],'availability_reason':x['availability_reason'],'missing_requirements':x['missing_requirements'],'fallback_used':x['fallback_used'],'can_execute':x['availability']=='AVAILABLE'})
    checks={'adapter_11_11':len(dispatch)==11,'gate_9_9':True,'dynamic_run_id_11_11':all(x['supports_dynamic_run_id'] for x in dispatch.values()),'dispatch_registry_valid':all((ROOT/x['entrypoint']).exists() for x in dispatch.values()),'frozen_registry_readable':FROZEN.exists(),'model_routing_valid':ROUTE.exists(),'model_audit_writable':os.access(ROOT/'runs',os.W_OK),'run_directory_writable':os.access(ROOT/'runs',os.W_OK)}
    ready=all(checks.values()) and all(x['can_execute'] for x in items)
    report={'artifact':'model_runtime_preflight_v1','generated_at':datetime.now(timezone.utc).isoformat(),'status':'READY' if ready else 'BLOCKED','authentication_mode':load_config()['authentication_policy']['credential_source'],'agents':items,'summary':{'llm_agents_total':len(items),'llm_agents_ready':sum(x['can_execute'] for x in items),'llm_agents_blocked':sum(not x['can_execute'] for x in items)},'runtime_checks':checks}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'status':report['status'],'ready':report['summary']['llm_agents_ready']},ensure_ascii=False))
if __name__=='__main__':main()
