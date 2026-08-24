#!/usr/bin/env python3
"""Static safety checks for a GitHub delivery candidate; no Agents are invoked."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = [
    "README.md", "requirements.txt", ".env.example", "scripts/run_customer_demand_analysis.py",
    "claude-view/app.js", "examples/input/README.md",
]
VIEW = [f"examples/demo-view/{number:02d}_{name}.json" for number, name in [
    (1, "run_overview"), (2, "agent_graph"), (3, "execution_timeline"), (4, "gate_status"),
    (5, "model_routing"), (6, "artifact_lineage"), (7, "warning_summary"),
    (8, "forecast_summary"), (9, "action_summary"), (10, "e2e_evidence"),
]]
SECRET = re.compile(r"(?:sk-[A-Za-z0-9_-]{12,}|sk-ant-[A-Za-z0-9_-]{12,}|AIza[\w-]{20,}|ghp_[\w]{20,}|github_pat_[\w]{20,}|AKIA[A-Z0-9]{16})")

def delivery_files() -> list[Path]:
    excluded = {".git", "runs", "artifacts", "quality", "logs", "data", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache"}
    return [path for path in ROOT.rglob("*") if path.is_file() and not any(part in excluded for part in path.relative_to(ROOT).parts)]

def main() -> None:
    missing = [name for name in [*REQUIRED, *VIEW] if not (ROOT / name).is_file()]
    inputs = sorted((ROOT / "examples/input").glob("*.xlsx"))
    failures = []
    if missing: failures.append(f"missing required delivery files: {missing}")
    if len(inputs) != 6: failures.append(f"expected six synthetic workbooks, found {len(inputs)}")
    ignored = subprocess.run(["git", "check-ignore", "-q", ".env.example"], cwd=ROOT).returncode == 0
    if ignored: failures.append(".env.example is ignored")
    tracked = [item for item in subprocess.run(["git", "ls-files", "runs", "artifacts", "quality", "logs", "data/raw"], cwd=ROOT, text=True, capture_output=True).stdout.splitlines() if not item.endswith(".gitkeep")]
    if tracked: failures.append(f"runtime or input data tracked: {tracked}")
    for path in delivery_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(ROOT)
        if ("/" + "Users/") in text: failures.append(f"absolute user path in delivery file: {rel}")
        if SECRET.search(text): failures.append(f"API-key pattern in delivery file: {rel}")
    if failures:
        print("FAIL")
        print("\n".join(failures))
        raise SystemExit(1)
    print("PASS")

if __name__ == "__main__": main()
