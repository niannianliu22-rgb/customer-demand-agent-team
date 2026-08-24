#!/usr/bin/env python3
"""Read the structured Supervisor runtime state for one run."""
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if len(sys.argv)!=2:raise SystemExit('Usage: python3 scripts/orchestration/run_status_v2.py RUN_ID')
p=ROOT/'runs'/sys.argv[1]/'state/runtime_state.json'
if not p.exists():raise SystemExit(f'Run not found: {sys.argv[1]}')
print(json.dumps(json.loads(p.read_text(encoding='utf-8')),ensure_ascii=False,indent=2))
