#!/usr/bin/env python3
"""Validate a materialized run before any business Agent is dispatched."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    args = parser.parse_args()
    run = ROOT / 'runs' / args.run_id
    manifest_path = run / 'run_manifest.json'
    input_manifest_path = run / 'input_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    input_manifest = json.loads(input_manifest_path.read_text(encoding='utf-8')) if input_manifest_path.exists() else {}
    a05 = (ROOT / 'scripts/data/standardize_demand_history.py').read_text(encoding='utf-8')
    a06 = (ROOT / 'scripts/data/run_data_quality_agent_v1.py').read_text(encoding='utf-8')
    schema_snapshot = run / 'snapshots/canonical_schema.json'
    schema = json.loads(schema_snapshot.read_text(encoding='utf-8')) if schema_snapshot.exists() else {}
    required_dirs = ['input', 'artifacts', 'gates', 'quality', 'audit', 'logs', 'snapshots']
    required_manifest_fields = {'run_id', 'created_at', 'target_month', 'workflow_version', 'schema_version', 'model_runtime_binding_version', 'model_routing_version', 'governance_version', 'frozen_registry_version', 'input_manifest', 'run_status'}
    snapshots = ['frozen_registry.json', 'model_registry.yaml', 'model_routing.yaml', 'model_runtime_binding.yaml', 'agent_governance.yaml', 'canonical_schema.json', 'business_rules.md', 'standardization_rules.yaml', 'workflow.yaml', 'dependency_graph.yaml', 'agent_dispatch_registry.yaml', 'gate_runtime_v1.py', 'gate_model_v2.md']
    sources = input_manifest.get('sources', [])
    live_binding = ROOT / 'config/models/model_runtime_binding_v1.yaml'
    binding_snapshot = run / 'snapshots/model_runtime_binding.yaml'
    sys.path.insert(0, str(ROOT / 'scripts/orchestration'))
    from model_runtime_adapter_v1 import resolve
    a10 = resolve('critical_maker_codex'); a11 = resolve('critical_checker_claude_opus')
    checks = {
        'required_directories_exist': all((run / name).is_dir() for name in required_dirs),
        'six_excel_inputs_materialized': len(sources) == 6 and len([p for p in (run / 'input').glob('*.xlsx')]) == 6,
        'input_manifest_exists': input_manifest_path.exists(),
        'input_manifest_is_immutable_and_matches_checksums': bool(input_manifest.get('immutable')) and all(item.get('immutable') is True and item.get('copied_or_linked') == 'copied' and (run / 'input' / item['source_filename']).exists() and sha(run / 'input' / item['source_filename']) == item['source_checksum'] for item in sources),
        'frozen_registry_snapshot_exists': (run / 'snapshots/frozen_registry.json').exists(),
        'required_configuration_snapshots_exist': all((run / 'snapshots' / name).exists() for name in snapshots),
        'schema_version_is_1_5_0': manifest.get('schema_version') == '1.5.0' and schema.get('schema_version') == '1.5.0',
        'a05_has_no_legacy_schema_version_hardcoding': 'schema_version"] != "1.0.0"' not in a05 and 'schema_gate_result.json' not in a05,
        'schema_gate_contract_is_run_bound': 'run_dir / "gates" / "SCHEMA_GATE.json"' in a05 and 'gate["decision"]' in a05,
        'a06_quality_outputs_are_run_bound': "QUALITY=ROOT/f'runs/{RUN_ID}/quality'" in a06 and "ROOT/'quality'" not in a06,
        'model_runtime_binding_snapshot_exists': (run / 'snapshots/model_runtime_binding.yaml').exists(),
        'model_runtime_binding_is_v3_0': yaml.safe_load(binding_snapshot.read_text(encoding='utf-8')).get('version') == '3.0',
        'model_runtime_binding_snapshot_matches_live': binding_snapshot.exists() and sha(binding_snapshot) == sha(live_binding),
        'claude_cli_available': resolve('medium_claude_sonnet')['availability'] == 'AVAILABLE',
        'codex_cli_available': resolve('medium_codex')['availability'] == 'AVAILABLE',
        'a10_concrete_binding': a10['provider'] == 'codex_cli' and a10['concrete_model'] == 'gpt-5.6-terra' and a10['reasoning_effort'] == 'xhigh',
        'a11_concrete_binding': a11['provider'] == 'claude_cli' and a11['concrete_model'] == 'claude-opus-5' and a11['reasoning_effort'] == 'max',
        'a10_a11_provider_isolation': a10['provider'] != a11['provider'],
        'adapter_registry_11_ready': len(yaml.safe_load((ROOT / 'config/orchestration/agent_dispatch_registry_v1.yaml').read_text(encoding='utf-8'))['agents']) == 11,
        'gate_contracts_9_ready': len(yaml.safe_load((ROOT / 'config/orchestration/workflow_v2.yaml').read_text(encoding='utf-8'))['gates']) == 9,
        'audit_path_writable': (run / 'audit').is_dir(),
        'run_manifest_is_complete': required_manifest_fields <= set(manifest),
        'run_status_is_ready': manifest.get('run_status') == 'READY' and json.loads((run / 'state/runtime_state.json').read_text(encoding='utf-8')).get('run_status') == 'READY',
    }
    report = {'artifact': 'run_initialization_preflight_v1', 'run_id': args.run_id, 'generated_at': datetime.now(timezone.utc).isoformat(), 'result': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks, 'ready_for_e2e_retry': all(checks.values())}
    output = run / 'logs/run_initialization_preflight.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'run_id': args.run_id, 'result': report['result'], 'ready_for_e2e_retry': report['ready_for_e2e_retry']}, ensure_ascii=False))
    if report['result'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
