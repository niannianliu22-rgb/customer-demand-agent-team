#!/usr/bin/env python3
"""Offline contract checks for CLI-login multi-provider runtime; never invokes a model."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/orchestration'))
from model_runtime_adapter_v1 import load_config, resolve


def main() -> None:
    cfg = load_config()
    bindings = cfg['bindings']
    checks = {
        'no_api_key_authentication': cfg['authentication_policy']['api_keys_allowed'] is False,
        'both_cli_providers_registered': set(cfg['providers']) == {'claude_cli', 'codex_cli'},
        'all_bindings_have_cli_provider': all(x['provider'] in cfg['providers'] for x in bindings.values()),
        'all_bindings_have_models': all(bool(x['concrete_model']) and bool(x['reasoning_effort']) for x in bindings.values()),
        'a10_a11_primary_provider_independent': bindings['critical_maker_codex']['provider'] != bindings['critical_checker_claude_opus']['provider'],
        'claude_noninteractive_command': '--effort' in __import__('model_runtime_adapter_v1')._command(resolve('medium_claude_sonnet', probe=False), 'x', ROOT / 'schemas/agent_model_output_envelope_v1.json', ROOT / 'tmp.json'),
        'codex_noninteractive_command': '--config' in __import__('model_runtime_adapter_v1')._command(resolve('medium_codex', probe=False), 'x', ROOT / 'schemas/agent_model_output_envelope_v1.json', ROOT / 'tmp.json'),
    }
    failed = [name for name, ok in checks.items() if not ok]
    print({'result': 'PASS' if not failed else 'FAIL', 'checks': checks})
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
