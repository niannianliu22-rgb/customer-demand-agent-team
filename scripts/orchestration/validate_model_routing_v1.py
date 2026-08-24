#!/usr/bin/env python3
"""Configuration-only QA for Model Routing V1. Never invokes models or Agents."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / 'config/agents/agent_registry_v2.yaml'
MODELS = ROOT / 'config/models/model_registry_v1.yaml'
ROUTING = ROOT / 'config/models/model_routing_v1.yaml'
OUT = ROOT / 'artifacts/orchestration_v2/model_routing_qa.json'

def load(path):
    return yaml.safe_load(path.read_text(encoding='utf-8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    registry, models, routing = load(REGISTRY), load(MODELS), load(ROUTING)
    by_id = {a['agent_id']: a for a in registry['agents']}
    routes = routing['routes']
    issues = []
    def check(name, condition, detail):
        if not condition:
            issues.append({'check': name, 'detail': detail})
        return condition
    ids = {f'A{i:02d}' for i in range(1, 14)}
    checks = {}
    checks['all_13_agents_registered'] = check('all_13_agents_registered', set(by_id) == ids and set(routes) == ids, 'Registry or routing misses an A01-A13 route.')
    checks['registry_routing_fields_match'] = check('registry_routing_fields_match', all(all(by_id[a].get(k) == routes[a].get(k) for k in ['execution_mode','model_tier','llm_enabled','llm_trigger','primary_model','fallback_model','reasoning_level','structured_output_schema']) and by_id[a].get('evidence_boundary') == a for a in ids), 'Agent registry metadata differs from routing metadata.')
    deterministic = {'A01','A02','A03','A06'}
    checks['required_deterministic_agents'] = check('required_deterministic_agents', all(routes[a]['model_tier'] == 'TIER_0_DETERMINISTIC' and routes[a]['llm_enabled'] is False for a in deterministic), 'A01/A02/A03/A06 must be deterministic with no LLM.')
    checks['a04_a05_exception_only'] = check('a04_a05_exception_only', all(routes[a]['model_tier'] == 'TIER_0_DETERMINISTIC' and routes[a]['llm_enabled'] == 'conditional' and 'candidate_only' in routes[a]['llm_output_constraints'] and 'human_review' in ' '.join(routes[a]['llm_output_constraints']) for a in ['A04','A05']), 'A04/A05 exception model policy invalid.')
    checks['a07_strong'] = check('a07_strong', routes['A07']['model_tier'] == 'TIER_2_STRONG_REASONING', 'A07 must be TIER_2.')
    checks['a08_hybrid'] = check('a08_hybrid', routes['A08']['execution_mode'].startswith('HYBRID') and routes['A08']['model_tier'] == 'TIER_1_MEDIUM' and routes['A08']['primary_model'] == 'medium_claude_sonnet' and routes['A08']['reasoning_level'] == 'HIGH', 'A08 concrete Claude Sonnet binding invalid.')
    checks['a09_strong'] = check('a09_strong', routes['A09']['model_tier'] == 'TIER_2_STRONG_REASONING', 'A09 must be TIER_2.')
    checks['a10_a11_critical'] = check('a10_a11_critical', all(routes[a]['model_tier'] == 'TIER_3_CRITICAL_REASONING' for a in ['A10','A11']) and routes['A10']['primary_model'] != routes['A11']['primary_model'] and models['models'][routes['A10']['primary_model']]['provider'] != models['models'][routes['A11']['primary_model']]['provider'] and routes['A10']['fallback_model'] == routes['A11']['fallback_model'] == 'NONE', 'A10/A11 maker-checker provider isolation invalid.')
    checks['a12_strong'] = check('a12_strong', routes['A12']['model_tier'] == 'TIER_2_STRONG_REASONING', 'A12 must be TIER_2.')
    checks['a13_medium'] = check('a13_medium', routes['A13']['model_tier'] == 'TIER_1_MEDIUM', 'A13 must be TIER_1.')
    checks['structured_and_bounded_llm'] = check('structured_and_bounded_llm', all(r.get('structured_output_schema') and r.get('evidence_boundary',{}).get('allowed_input_artifacts') and r.get('evidence_boundary',{}).get('forbidden_sources') for r in routes.values()), 'Every route requires schema and evidence boundary.')
    checks['gates_deterministic'] = check('gates_deterministic', routing['global_policy']['gates_decided_by'] == 'DETERMINISTIC_STRUCTURED_ARTIFACTS_ONLY', 'Gate policy is not deterministic.')
    checks['frozen_rules_read_only'] = check('frozen_rules_read_only', routing['global_policy']['frozen_rules_modifiable_by_llm'] is False, 'LLM must not modify frozen rules.')
    checks['critical_fallback_not_downgraded'] = check('critical_fallback_not_downgraded', all(routes[a]['fallback_model'] == 'NONE' for a in ['A10','A11']), 'Critical Agents must block rather than cross-provider fallback.')
    checks['audit_complete'] = check('audit_complete', set(routing['model_call_audit']['required_fields']) == {'run_id','agent_id','model_tier','model_name','reasoning_level','fallback_used','input_artifact_checksum','output_artifact_checksum','started_at','completed_at','status'} and routing['model_call_audit']['forbidden_fields'] == ['prompt','system_prompt','user_prompt','raw_sensitive_content'], 'Model call audit fields invalid.')
    checks['dry_run_no_llm'] = check('dry_run_no_llm', routing['global_policy']['dry_run_llm_calls'] == 0, 'Dry run must make zero model calls.')
    result = 'PASS' if all(checks.values()) else 'FAIL'
    report = {'artifact':'model_routing_qa_v1','generated_at':datetime.now(timezone.utc).isoformat(),'result':result,'dry_run_llm_calls':0,'checks':checks,'issues':issues,'input_checksums':{str(p.relative_to(ROOT)):sha(p) for p in [REGISTRY, MODELS, ROUTING]},'model_call_audit_path_pattern':routing['model_call_audit']['artifact_path_pattern']}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'result':result,'artifact':str(OUT.relative_to(ROOT))}, ensure_ascii=False))
    if result != 'PASS':
        raise SystemExit(1)

if __name__ == '__main__':
    main()
