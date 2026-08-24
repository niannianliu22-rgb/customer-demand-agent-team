#!/usr/bin/env python3
"""Read-only QA for A05's run-snapshot standardization version contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument('run_id'); args = parser.parse_args()
    run = ROOT / 'runs' / args.run_id
    rules = run / 'snapshots/standardization_rules.yaml'; business = run / 'snapshots/business_rules.md'
    source = (ROOT / 'scripts/data/standardize_demand_history.py').read_text(encoding='utf-8')
    version = yaml.safe_load(rules.read_text(encoding='utf-8')).get('rules_version')
    match = re.search(r'Business Rules Version:\s*([^*\n]+)', business.read_text(encoding='utf-8'))
    identity = match.group(1).strip() if match else sha(business)
    checks = {
        'no_hardcoded_2_0': 'rules_version"] != "2.0"' not in source and 'Business Rules Version: 2.0' not in source,
        'reads_run_snapshots': 'rules_snapshot = run_dir / "snapshots" / "standardization_rules.yaml"' in source and 'business_rules_snapshot = run_dir / "snapshots" / "business_rules.md"' in source,
        'snapshot_rules_version_19_0': str(version) == '19.0',
        'business_rules_has_declared_version': match is not None,
        'business_and_standardization_versions_match': identity == str(version),
        'live_rules_unchanged_from_snapshot': sha(rules) == sha(ROOT / 'config/data/standardization_rules.yaml'),
        'live_business_rules_unchanged_from_snapshot': sha(business) == sha(ROOT / 'policies/business_rules.md'),
        'a03_a04_artifacts_preserved': (run / 'artifacts/source_manifest.json').exists() and (run / 'artifacts/schema_mapping.json').exists(),
    }
    report = {'artifact': 'standardization_contract_qa_v1', 'run_id': args.run_id, 'result': 'PASS' if all(checks.values()) else 'FAIL', 'authoritative_standardization_rules_version': version, 'authoritative_business_rules_identity': {'type': 'DECLARED_VERSION' if match else 'CHECKSUM', 'value': identity, 'checksum': sha(business)}, 'checks': checks, 'ready_for_a05_resume': all(checks.values())}
    print(json.dumps(report, ensure_ascii=False))
    if report['result'] != 'PASS': raise SystemExit(1)


if __name__ == '__main__': main()
