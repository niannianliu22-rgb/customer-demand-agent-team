#!/usr/bin/env python3
"""Delivery-facing entry point for one governed customer-demand run.

It delegates all workflow work to the existing A01 Supervisor CLI.  It never
dispatches individual A03–A13 Agents itself.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR = ROOT / "scripts/orchestration/run_agent_team_v2.py"

def invoke(arguments: list[str]) -> dict:
    result = subprocess.run([sys.executable, str(SUPERVISOR), *arguments], cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Supervisor command failed")
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Supervisor returned non-JSON output: {result.stdout.strip()}") from error

def validate_input(source: Path) -> Path:
    source = source.expanduser().resolve()
    if not source.is_dir(): raise ValueError(f"Input source directory not found: {source}")
    files = sorted(item for item in source.iterdir() if item.is_file() and item.suffix.lower() == ".xlsx" and not item.name.startswith("."))
    if len(files) != 6: raise ValueError(f"Exactly six .xlsx input files are required; found {len(files)} in {source}")
    return source

def summary(run_id: str, name: str, count_key: str) -> dict:
    path = ROOT / "runs" / run_id / "artifacts" / name
    if not path.exists(): return {"available": False}
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get(count_key, [])
    return {"available": True, "count": len(items) if isinstance(items, list) else None}

def main() -> None:
    parser = argparse.ArgumentParser(description="Run Customer Demand Analysis through A01 Supervisor.")
    parser.add_argument("--target-month", required=True, help="Target month in YYYY-MM format.")
    parser.add_argument("--source-input-dir", required=True, help="Directory containing exactly six .xlsx inputs.")
    parser.add_argument("--initialize-only", action="store_true", help="Create and validate a new run without invoking business Agents.")
    args = parser.parse_args()
    try:
        source = validate_input(Path(args.source_input_dir))
        initialized = invoke(["--target-month", args.target_month, "--source-input-dir", str(source)])
        run_id = initialized["run_id"]
        if args.initialize_only:
            final = initialized
        else:
            final = invoke(["--execute", run_id])
        state = json.loads((ROOT / "runs" / run_id / "state/runtime_state.json").read_text(encoding="utf-8"))
        print(json.dumps({
            "RUN_ID": run_id,
            "RUN_STATUS": state["run_status"],
            "FORECAST_SUMMARY": summary(run_id, "forecast/forecast_report.json", "forecasts"),
            "ACTION_SUMMARY": summary(run_id, "action/action_plan.json", "actions"),
            "CLAUDE_VIEW_URL": f"http://localhost:8080/claude-view/?run_id={run_id}",
            "SUPERVISOR_RESULT": final,
        }, ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError, KeyError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"RUN_STATUS": "FAILED", "ERROR": str(error)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)

if __name__ == "__main__": main()
