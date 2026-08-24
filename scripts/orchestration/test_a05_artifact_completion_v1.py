#!/usr/bin/env python3
"""Read-only QA for the A05→A06 standardization-audit artifact contract."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(run_id: str) -> dict:
    run = ROOT / "runs" / run_id
    artifacts = run / "artifacts"
    dataset = artifacts / "unified_dataset.csv"
    gate = run / "gates" / "STANDARDIZATION_GATE.json"
    contract_path = ROOT / "config/orchestration/artifact_contract_v1.yaml"
    dispatch_path = ROOT / "config/orchestration/agent_dispatch_registry_v1.yaml"
    task_path = artifacts / "task_type_standardization_v17_audit.json"
    channel_path = artifacts / "channel_standardization_v1_audit.json"
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    dispatch = yaml.safe_load(dispatch_path.read_text(encoding="utf-8"))["agents"]
    gate_payload = json.loads(gate.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {
        "standardized_dataset_exists": dataset.is_file(),
        "standardization_gate_remains_pass": gate_payload.get("decision") == "PASS" and gate_payload.get("run_id") == run_id,
        "a05_dispatch_declares_both_audits": all(path in dispatch["A05"]["expected_outputs"] for path in ["artifacts/task_type_standardization_v17_audit.json", "artifacts/channel_standardization_v1_audit.json"]),
        "a06_dispatch_requires_both_audits": all(path in dispatch["A06"]["required_inputs"] for path in ["artifacts/task_type_standardization_v17_audit.json", "artifacts/channel_standardization_v1_audit.json"]),
    }
    import csv
    with dataset.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    checks["school_standardization_complete"] = bool(rows) and all(row.get("school_standardization_status") and row.get("school_rule_id") and row.get("school_rule_version") for row in rows) and not any(row.get("school_standardization_status") == "UNSTANDARDIZED" for row in rows)
    checks["task_type_standardization_complete"] = bool(rows) and all(row.get("task_type_standardization_status") and row.get("task_type_rule_id") and row.get("task_type_rule_version") for row in rows) and not any(row.get("task_type_standardization_status") == "UNMATCHED" for row in rows)
    checks["channel_standardization_complete"] = bool(rows) and all(row.get("channel_standardization_status") == "STANDARDIZED" and row.get("channel_rule_id") and row.get("channel_rule_version") for row in rows)
    checks["date_standardization_lineage_complete"] = bool(rows) and all("consultation_date_original" in row and "ddl_original" in row and "consultation_date" in row and "ddl" in row for row in rows)
    audits = {}
    for name, path, key in [("task_type", task_path, "task_type_standardization_audit"), ("channel", channel_path, "channel_standardization_audit")]:
        item = contract["artifacts"][key]
        valid = path.is_file()
        payload = json.loads(path.read_text(encoding="utf-8")) if valid else {}
        checks[f"{name}_audit_exists"] = valid
        checks[f"{name}_audit_run_bound"] = valid and payload.get("run_id") == run_id and payload.get("producer_agent") == "A05"
        checks[f"{name}_audit_registry_contract"] = item["producer_agent"] == "A05" and "A06" in item["consumer_agents"] and item["required_by"] == "DATA_QUALITY_AGENT"
        checks[f"{name}_source_checksum_traceable"] = valid and payload.get("source_checksums", {}).get("standardized_dataset") == sha256(dataset)
        checks[f"{name}_does_not_reuse_old_run"] = valid and payload.get("lineage", {}).get("old_run_artifact_used") is False
        checks[f"{name}_audit_result_pass"] = valid and payload.get("result") == "PASS"
        audits[name] = {"path": str(path.relative_to(run)), "result": payload.get("result"), "run_id": payload.get("run_id"), "producer_agent": payload.get("producer_agent"), "source_dataset_checksum": payload.get("source_checksums", {}).get("standardized_dataset")}
    checks["a05_to_a06_contract_registered"] = all(checks[key] for key in ["a05_dispatch_declares_both_audits", "a06_dispatch_requires_both_audits", "task_type_audit_registry_contract", "channel_audit_registry_contract"])
    report = {"run_id": run_id, "qa_name": "A05_ARTIFACT_COMPLETION_QA", "checked_at": datetime.now(timezone.utc).isoformat(), "audits": audits, "checks": checks, "result": "PASS" if all(checks.values()) else "FAIL", "a06_input_contract": "PASS" if all(checks[key] for key in ["standardized_dataset_exists", "school_standardization_complete", "task_type_standardization_complete", "channel_standardization_complete", "date_standardization_lineage_complete", "task_type_audit_exists", "channel_audit_exists", "task_type_audit_run_bound", "channel_audit_run_bound", "task_type_audit_result_pass", "channel_audit_result_pass", "a05_to_a06_contract_registered"]) else "FAIL"}
    (run / "audit" / "a05_artifact_completion_qa.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: test_a05_artifact_completion_v1.py <RUN_ID>")
    report = main(sys.argv[1])
    print(json.dumps({"result": report["result"], "a06_input_contract": report["a06_input_contract"]}, ensure_ascii=False))
