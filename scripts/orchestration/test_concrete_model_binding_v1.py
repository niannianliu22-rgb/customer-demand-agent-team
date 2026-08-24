#!/usr/bin/env python3
"""Minimal non-business runtime tests for the final concrete model bindings."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/orchestration'))
from model_runtime_adapter_v1 import invoke, resolve

SCHEMA = ROOT / 'schemas/agent_model_output_envelope_v1.json'
OUT = ROOT / 'artifacts/runtime_execution_v1/concrete_model_binding_test.json'
CASES = {
    'A07': ('strong_codex', 'TIER_2_STRONG_REASONING', 'gpt-5.6-terra', 'high', 'codex_cli'),
    'A10': ('critical_maker_codex', 'TIER_3_CRITICAL_REASONING', 'gpt-5.6-terra', 'xhigh', 'codex_cli'),
    'A11': ('critical_checker_claude_opus', 'TIER_3_CRITICAL_REASONING', 'claude-opus-5', 'max', 'claude_cli'),
    'A13': ('medium_claude_sonnet_medium', 'TIER_1_MEDIUM', 'claude-sonnet-5', 'medium', 'claude_cli'),
}


def prompt(agent: str, tier: str) -> str:
    return (f'Return only the required JSON object. This is a non-business binding check. '
            f'Set agent_id to {agent}; model_tier to {tier}; status to BINDING_OK; confidence to null; '
            'evidence_refs and warnings to empty arrays; contract_payload summary to "binding ok", '
            'findings and recommendations to empty arrays, and return_to_agent to null. Do not inspect files or run tools.')


def main() -> None:
    results = []
    for agent, (alias, tier, model, effort, provider) in CASES.items():
        expected_response = {'agent_id': agent, 'model_tier': tier, 'status': 'BINDING_OK', 'confidence': None, 'evidence_refs': [], 'warnings': [], 'contract_payload': {'summary': 'binding ok', 'findings': [], 'recommendations': [], 'return_to_agent': None}}
        try:
            response, audit = invoke(alias, prompt(agent, tier), SCHEMA, timeout=180)
            checks = {
                'response_contract': response == expected_response,
                'provider': audit['model_name'].startswith(f'{provider}:'),
                'concrete_model': audit['actual_model'] == model,
                'effort': audit['actual_effort'] == effort,
                'explicit_model': audit['explicit_model_argument'],
                'explicit_effort': audit['explicit_effort_argument'],
            }
            results.append({'agent_id': agent, 'expected': {'provider': provider, 'concrete_model': model, 'reasoning_effort': effort}, 'actual': audit, 'checks': checks})
        except Exception as exc:
            results.append({'agent_id': agent, 'expected': {'provider': provider, 'concrete_model': model, 'reasoning_effort': effort}, 'actual': {'error': str(exc)}, 'checks': {'response_contract': False, 'provider': False, 'concrete_model': False, 'effort': False, 'explicit_model': False, 'explicit_effort': False}})
    checks = {
        'claude_cli_available': resolve('medium_claude_sonnet')['availability'] == 'AVAILABLE',
        'codex_cli_available': resolve('medium_codex')['availability'] == 'AVAILABLE',
        'a07_high': results[0]['checks']['effort'], 'a10_terra_xhigh': results[1]['checks']['concrete_model'] and results[1]['checks']['effort'],
        'a11_claude_opus_max': all(results[2]['checks'][x] for x in ['provider', 'concrete_model', 'effort']),
        'a13_claude_sonnet_medium': all(results[3]['checks'][x] for x in ['provider', 'concrete_model', 'effort']),
        'maker_checker_provider_isolation': results[1]['expected']['provider'] != results[2]['expected']['provider'],
        'no_default_login_model': all(item['actual'].get('configured_model') != 'DEFAULT_LOGIN_MODEL' for item in results),
        'no_default_effort': all(item['actual'].get('explicit_effort') for item in results),
    }
    report = {'artifact': 'concrete_model_binding_test_v1', 'generated_at': datetime.now(timezone.utc).isoformat(), 'result': 'PASS' if all(checks.values()) and all(all(x['checks'].values()) for x in results) else 'FAIL', 'results': results, 'checks': checks}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'result': report['result'], 'checks': checks}, ensure_ascii=False))
    if report['result'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
