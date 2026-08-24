#!/usr/bin/env python3
"""Recover A07 only from its first successful persisted model response."""
from __future__ import annotations
# INTERNAL / HISTORICAL RECOVERY ONLY: this script deliberately addresses the
# frozen 2026-08 baseline and is not a delivery-facing or Quick Start command.
import hashlib, json, os, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUN_ID='RUN-202608-TEAM-20260823T185333'
RUN=ROOT/'runs'/RUN_ID
EXPECTED='9a7410f87f6716de451a1426446b7bdd6d8810958fdccf3399e47825cf1f6dc6'
RAW=RUN/'audit/model_raw_outputs/CALL-676897ac0b8f4b2db0575cfa1dbd9778_model_content.txt'
TARGET=RUN/'artifacts/historical_demand/historical_demand_report.json'

def sha(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    sys.path.insert(0,str(ROOT/'scripts/orchestration'))
    from model_output_envelope_adapter_v1 import normalize_provider_output, build_agent_model_output_envelope
    if not RAW.exists() or not TARGET.exists(): raise SystemExit('RECOVERY_EVIDENCE_MISSING')
    raw=RAW.read_text(encoding='utf-8')
    payload=normalize_provider_output('codex_cli',raw,'')
    envelope=build_agent_model_output_envelope({'agent_id':'A07','model_tier':'TIER_2_STRONG_REASONING'},payload)
    expected_raw=hashlib.sha256(raw.encode()).hexdigest()
    if expected_raw!='0862dc61a34c5996fd4f0042d03af2ba65e5d2ac0af1637563e1d1a928d861d6': raise SystemExit('RECOVERY_RAW_CHECKSUM_MISMATCH')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    quarantine=RUN/'audit/artifact_quarantine'/f'{stamp}_a07_overwritten_report.json'
    quarantine.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(TARGET,quarantine)
    envelope_path=RUN/'audit/model_output_envelopes/A07_first_success_recovered.json'; envelope_path.write_text(json.dumps(envelope,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.environ.update({'CDAT_RUN_ID':RUN_ID,'CDAT_TARGET_MONTH':'2026-08','CDAT_AGENT_ID':'A07','CDAT_MODEL_OUTPUT_ENVELOPE':str(envelope_path)})
    sys.path.insert(0,str(ROOT/'scripts/data'))
    import run_a07_a08_context_agents_v2 as writer
    writer.a07()
    recovered=sha(TARGET)
    if recovered!=EXPECTED:
        shutil.copy2(quarantine,TARGET)
        raise SystemExit(f'RECOVERY_CHECKSUM_MISMATCH:{recovered}')
    audit={'run_id':RUN_ID,'agent_id':'A07','recovery_method':'persisted_first_success_raw_response_plus_deterministic_artifact_writer','source_call_id':'CALL-676897ac0b8f4b2db0575cfa1dbd9778','source_raw_checksum':expected_raw,'expected_artifact_checksum':EXPECTED,'recovered_artifact_checksum':recovered,'quarantined_overwritten_artifact':str(quarantine.relative_to(RUN)),'recovered_model_output_envelope':str(envelope_path.relative_to(RUN)),'status':'PASS','recovered_at':datetime.now(timezone.utc).isoformat()}
    (RUN/'audit/a07_artifact_recovery_v1.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(audit,ensure_ascii=False))
if __name__=='__main__': main()
