#!/usr/bin/env python3
"""Append a prompt-free, machine-readable Model Call Audit event for A02."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {'run_id','agent_id','model_tier','model_name','reasoning_level','fallback_used','input_artifact_checksum','output_artifact_checksum','started_at','completed_at','status'}
FORBIDDEN = {'prompt','system_prompt','user_prompt','raw_sensitive_content'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    parser.add_argument('--event-json', required=True, help='Path to one structured audit event JSON file.')
    args = parser.parse_args()
    event = json.loads(Path(args.event_json).read_text(encoding='utf-8'))
    if event.get('run_id') != args.run_id:
        raise SystemExit('run_id does not match audit event')
    missing = REQUIRED - event.keys()
    forbidden = FORBIDDEN & event.keys()
    if missing or forbidden:
        raise SystemExit(f'invalid audit event: missing={sorted(missing)} forbidden={sorted(forbidden)}')
    path = ROOT / 'runs' / args.run_id / 'audit' / 'model_call_audit.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(json.dumps({'status':'RECORDED','artifact':str(path.relative_to(ROOT))}, ensure_ascii=False))

if __name__ == '__main__':
    main()
