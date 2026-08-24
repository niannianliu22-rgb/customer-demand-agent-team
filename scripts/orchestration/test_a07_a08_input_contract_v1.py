#!/usr/bin/env python3
"""Read-only QA for the A06→A07/A08 evidence and warning handoff."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2]
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main(run_id):
    run=ROOT/'runs'/run_id
    code=(ROOT/'scripts/data/run_a07_a08_context_agents_v2.py').read_text(encoding='utf-8')
    contract=yaml.safe_load((ROOT/'config/orchestration/artifact_contract_v1.yaml').read_text())['artifacts']
    dispatch=yaml.safe_load((ROOT/'config/orchestration/agent_dispatch_registry_v1.yaml').read_text())['agents']
    manifest=json.loads((run/'snapshots/frozen_evidence_manifest.json').read_text())
    ledger=json.loads((run/'audit/warning_ledger.json').read_text())
    support=json.loads((run/'artifacts/support_school_universe.json').read_text())
    checks={
      'a07_no_global_quality_read':'ROOT / "quality"' not in code and 'DQ = contract_path("data_quality_report")' in code,
      'a07_a06_inputs_run_bound':all((run/p).exists() for p in ['artifacts/unified_dataset.csv','quality/quality_report.json','quality/data_quality_issues.csv','quality/data_quality_gate_report.json','audit/warning_ledger.json']),
      'a07_frozen_historical_snapshot':(run/contract['frozen_historical_evidence']['path']).is_dir(),
      'a08_frozen_inputs_not_outputs':'snapshots/frozen_evidence/academic_context_evidence_v1' in dispatch['A08']['required_inputs'] and 'artifacts/academic_context/academic_context_report.json' not in dispatch['A08']['required_inputs'],
      'a08_frozen_calendar_snapshot':(run/contract['frozen_academic_context_evidence']['path']).is_dir(),
      'support_school_run_bound':support['run_id']==run_id and support['source_checksum']==sha(run/'artifacts/unified_dataset.csv') and bool(support['schools']),
      'frozen_evidence_checksums':manifest['result']=='PASS' and all(x['source_checksum']==x['snapshot_checksum'] for x in manifest['entries']),
      'warning_ledger_active':ledger['run_id']==run_id and ledger['warning_count']==40 and ledger['propagation_status']=='ACTIVE' and set(ledger['consumer_agents'])=={'A07','A08','A09','A10','A11','A12','A13'},
      'data_quality_gate_preserves_warnings':json.loads((run/'gates/DATA_QUALITY_GATE.json').read_text()).get('decision')=='PASS_WITH_WARNINGS',
    }
    report={'run_id':run_id,'checks':checks,'result':'PASS' if all(checks.values()) else 'FAIL','calendar_producer':'academic_calendar_deterministic_pipeline_v1','academic_mapping_producer':'academic_calendar_deterministic_pipeline_v1','promotion_window_producer':'academic_calendar_deterministic_pipeline_v1'}
    (run/'audit/a07_a08_input_contract_qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__': main(sys.argv[1])
