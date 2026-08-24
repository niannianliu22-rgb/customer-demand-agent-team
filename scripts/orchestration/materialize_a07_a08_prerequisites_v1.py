#!/usr/bin/env python3
"""A01-owned, run-bound prerequisite materialization for the A07/A08 wave.

This is deliberately not a business Agent.  It freezes the registered
historical/calendar evidence into the current run and derives A05's support
school universe after (and only after) a passing A06 Data Quality Gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(run_id: str) -> dict:
    run = ROOT / "runs" / run_id
    state_path = run / "state/runtime_state.json"
    if not state_path.is_file():
        raise SystemExit(f"Run not found: {run_id}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    gate = state.get("gates", {}).get("DATA_QUALITY_GATE", {}).get("decision")
    if gate not in {"PASS", "PASS_WITH_WARNINGS"}:
        raise SystemExit("A07/A08 prerequisite materialization requires a passing DATA_QUALITY_GATE")

    required = [
        "artifacts/unified_dataset.csv",
        "quality/quality_report.json",
        "quality/data_quality_issues.csv",
        "quality/data_quality_gate_report.json",
        "audit/warning_ledger.json",
    ]
    missing = [rel for rel in required if not (run / rel).is_file()]
    if missing:
        raise SystemExit(f"A06 prerequisite artifacts missing: {missing}")

    frozen_manifest = run / "snapshots/frozen_evidence_manifest.json"
    support = run / "artifacts/support_school_universe.json"
    frozen_root = run / "snapshots/frozen_evidence"
    existing = [frozen_manifest.exists(), support.exists()]
    if any(existing) and not all(existing):
        raise SystemExit("Partial A07/A08 prerequisite materialization detected; immutable run inputs must be repaired explicitly")

    commands = []
    if not all(existing):
        commands = [
            ROOT / "scripts/orchestration/materialize_frozen_evidence_v1.py",
            ROOT / "scripts/orchestration/materialize_support_school_universe_v1.py",
        ]
        for script in commands:
            result = subprocess.run([sys.executable, str(script), run_id], cwd=ROOT, text=True, capture_output=True)
            if result.returncode:
                raise SystemExit(f"{script.name} failed: {result.stderr.strip() or result.stdout.strip()}")

    expected_dirs = [
        frozen_root / "historical_evidence_v1",
        frozen_root / "academic_context_evidence_v1",
    ]
    if not frozen_manifest.is_file() or not all(path.is_dir() for path in expected_dirs) or not support.is_file():
        raise SystemExit("A07/A08 prerequisite materialization did not produce the registered run-bound inputs")
    frozen = json.loads(frozen_manifest.read_text(encoding="utf-8"))
    support_payload = json.loads(support.read_text(encoding="utf-8"))
    dataset = run / "artifacts/unified_dataset.csv"
    checks = {
        "data_quality_gate_passed": gate in {"PASS", "PASS_WITH_WARNINGS"},
        "frozen_evidence_checksum_verified": frozen.get("result") == "PASS" and all(
            entry.get("source_checksum") == entry.get("snapshot_checksum") for entry in frozen.get("entries", [])
        ),
        "historical_and_academic_snapshots_present": all(path.is_dir() for path in expected_dirs),
        "support_school_universe_is_run_bound": support_payload.get("run_id") == run_id
        and support_payload.get("source_checksum") == sha(dataset)
        and bool(support_payload.get("schools")),
        "a06_inputs_unchanged": all((run / rel).is_file() for rel in required),
    }
    report = {
        "artifact": "a07_a08_prerequisite_materialization_v1",
        "run_id": run_id,
        "producer_agent": "A01",
        "stage": "A06_TO_A07_A08_PREREQUISITE_MATERIALIZATION",
        "materialized_at": now(),
        "mode": "MATERIALIZED" if commands else "REVALIDATED_EXISTING",
        "data_quality_gate_decision": gate,
        "outputs": [
            "snapshots/frozen_evidence_manifest.json",
            "snapshots/frozen_evidence/historical_evidence_v1",
            "snapshots/frozen_evidence/academic_context_evidence_v1",
            "artifacts/support_school_universe.json",
        ],
        "checks": checks,
        "result": "PASS" if all(checks.values()) else "FAIL",
    }
    write_json(run / "audit/a07_a08_prerequisite_materialization.json", report)
    if report["result"] != "PASS":
        raise SystemExit("A07/A08 prerequisite materialization validation failed")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    args = parser.parse_args()
    report = main(args.run_id)
    print(json.dumps({"run_id": args.run_id, "result": report["result"], "mode": report["mode"]}, ensure_ascii=False))
