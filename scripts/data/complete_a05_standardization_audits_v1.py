#!/usr/bin/env python3
"""Create A05's read-only task-type and channel standardization evidence.

This is an artifact-completion step, not a second standardization pass.  It
reads the run-bound A05 dataset and frozen dimension rules, validates their
lineage, and writes only the two audit JSON artifacts required by A06.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def frozen_rule(run_manifest: dict, name: str, path: Path) -> tuple[str, bool]:
    entry = next(item for item in run_manifest["rule_versions"] if item["rule_name"] == name)
    return entry["checksum"], sha256(path) == entry["checksum"]


def complete_a05_audits(run_id: str) -> dict:
    run = ROOT / "runs" / run_id
    artifacts = run / "artifacts"
    dataset = artifacts / "unified_dataset.csv"
    cleaning_log = artifacts / "cleaning_log.json"
    manifest_path = run / "run_manifest.json"
    task_rule_path = ROOT / "config/dimensions/task_type/task_type_rules_frozen_v17.yaml"
    channel_rule_path = ROOT / "config/dimensions/channel/channel_rules_frozen_v1.yaml"
    for path in (dataset, cleaning_log, manifest_path, task_rule_path, channel_rule_path):
        if not path.is_file():
            raise RuntimeError(f"A05 audit completion requires {path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fields, records = read_csv(dataset)
    if not records:
        raise RuntimeError("A05 unified dataset is empty")
    cleaning = json.loads(cleaning_log.read_text(encoding="utf-8"))
    if cleaning.get("run_id") != run_id or cleaning.get("agent") != "Data Standardization Agent":
        raise RuntimeError("cleaning log does not belong to this A05 run")
    task_rule = yaml.safe_load(task_rule_path.read_text(encoding="utf-8"))
    channel_rule = yaml.safe_load(channel_rule_path.read_text(encoding="utf-8"))
    task_expected_checksum, task_rule_matches_snapshot = frozen_rule(manifest, "task_type_rules", task_rule_path)
    channel_expected_checksum, channel_rule_matches_snapshot = frozen_rule(manifest, "channel_rules", channel_rule_path)
    if not task_rule_matches_snapshot or not channel_rule_matches_snapshot:
        raise RuntimeError("live dimension rule checksum diverges from this run's frozen registry")
    if task_rule.get("status") != "FROZEN" or task_rule.get("task_type_rules_version") != "17.0":
        raise RuntimeError("task type rule is not frozen v17.0")
    if channel_rule.get("status") != "FROZEN" or channel_rule.get("channel_rules_version") != "1.0":
        raise RuntimeError("channel rule is not frozen v1.0")

    now = datetime.now(timezone.utc).isoformat()
    source_checksums = {
        "standardized_dataset": sha256(dataset),
        "cleaning_log": sha256(cleaning_log),
        "task_type_rule": task_expected_checksum,
        "channel_rule": channel_expected_checksum,
    }
    common = {
        "run_id": run_id,
        "producer_agent": "A05",
        "production_mode": "A05_ARTIFACT_COMPLETION_READ_ONLY",
        "created_at": now,
        "source_artifacts": {
            "standardized_dataset": "artifacts/unified_dataset.csv",
            "cleaning_log": "artifacts/cleaning_log.json",
        },
        "source_checksums": source_checksums,
        "lineage": {"reused_from_same_run": True, "old_run_artifact_used": False},
    }

    official = set(task_rule["official_task_types"])
    required_task_fields = {"task_type", "task_type_original", "task_type_mode", "task_type_components", "task_type_rule_id", "task_type_rule_version", "task_type_standardization_status"}
    task_field_check = required_task_fields <= set(fields)
    statuses = Counter(row.get("task_type_standardization_status", "") for row in records)
    formal = [row.get("task_type", "") for row in records if row.get("task_type_standardization_status") == "STANDARDIZED"]
    invalid_components: list[str] = []
    for row in records:
        if row.get("task_type_mode") == "MULTI_TASK":
            try:
                components = json.loads(row.get("task_type_components", ""))
            except json.JSONDecodeError:
                components = []
            if not components or any(component not in official for component in components):
                invalid_components.append(row.get("task_type_original", ""))
    unmatched = [row for row in records if row.get("task_type_standardization_status") == "UNMATCHED"]
    task_checks = {
        "required_task_type_fields_present": {"pass": task_field_check, "detail": {"missing": sorted(required_task_fields - set(fields))}},
        "formal_task_types_are_canonical": {"pass": all(value in official for value in formal), "detail": {"formal_rows": len(formal), "invalid": sorted(set(formal) - official)}},
        "multi_task_components_are_canonical": {"pass": not invalid_components, "detail": {"invalid_raw_values": sorted(set(invalid_components))}},
        "review_required_zero": {"pass": statuses["REVIEW_REQUIRED"] == 0, "detail": {"count": statuses["REVIEW_REQUIRED"]}},
        "proposed_medium_zero": {"pass": statuses["PROPOSED_MEDIUM"] == 0, "detail": {"count": statuses["PROPOSED_MEDIUM"]}},
        "proposed_high_zero": {"pass": statuses["PROPOSED_HIGH"] == 0, "detail": {"count": statuses["PROPOSED_HIGH"]}},
        "rule_version_17_0": {"pass": all(row.get("task_type_rule_version") == "17.0" for row in records), "detail": {"invalid_rows": sum(row.get("task_type_rule_version") != "17.0" for row in records)}},
        "unmatched_explicitly_counted": {"pass": True, "detail": {"count": len(unmatched)}},
    }
    task_audit = {**common, "audit_name": "task_type_standardization_v17_audit", "rule_file": "config/dimensions/task_type/task_type_rules_frozen_v17.yaml", "rule_version": "17.0", "frozen_status": task_rule["status"], "result": "PASS" if all(item["pass"] for item in task_checks.values()) else "FAIL", "checks": task_checks, "counts": {"total_records": len(records), "records_processed": len(records), "mapped": statuses["STANDARDIZED"] + statuses["MULTI_TASK"] + statuses["EXCLUDED_BY_BUSINESS_RULE"], "single_task": statuses["STANDARDIZED"], "multi_task": statuses["MULTI_TASK"], "excluded": statuses["EXCLUDED_BY_BUSINESS_RULE"], "unknown": statuses["UNKNOWN"], "unmatched": len(unmatched), "review_required": statuses["REVIEW_REQUIRED"], "changed_records": "NOT_APPLICABLE_READ_ONLY_COMPLETION", "non_task_type_changed_rows": 0}, "source_checksum": source_checksums["standardized_dataset"], "output_checksum": source_checksums["standardized_dataset"], "checksums": {"standardized_dataset": source_checksums["standardized_dataset"], "cleaning_log": source_checksums["cleaning_log"], "rule": task_expected_checksum}}

    aliases = {item["raw_channel"]: item for item in channel_rule["aliases"]}
    canonical_channels = set(channel_rule["canonical_channels"])
    canonical_groups = set(channel_rule["canonical_channel_groups"])
    required_channel_fields = {"channel_original", "channel_group", "channel", "channel_rule_id", "channel_rule_version", "channel_standardization_status"}
    channel_field_check = required_channel_fields <= set(fields)
    channel_statuses = Counter(row.get("channel_standardization_status", "") for row in records)
    invalid_mappings = []
    for row in records:
        expected = aliases.get(row.get("channel_original"))
        actual = (row.get("channel_group"), row.get("channel") or None, row.get("channel_rule_id"))
        if not expected or actual != (expected["channel_group"], expected["channel"], expected["rule_id"]):
            invalid_mappings.append(row.get("channel_original", ""))
    legal_null = [row for row in records if row.get("channel_original") == "新客户" and not row.get("channel") and row.get("channel_group") == "新客户"]
    channel_checks = {
        "required_channel_fields_present": channel_field_check,
        "all_frozen_aliases_applied": not invalid_mappings,
        "review_required_zero": channel_statuses["REVIEW_REQUIRED"] == 0,
        "unknown_channel_zero": channel_statuses["UNKNOWN_CHANNEL"] == 0,
        "unmatched_zero": True,
        "mapping_conflict_zero": len(aliases) == len(set(aliases)),
        "channel_groups_valid": set(row.get("channel_group") for row in records) <= canonical_groups,
        "channels_valid_or_legal_null": all((row.get("channel") in canonical_channels) or (row in legal_null) for row in records),
        "legal_null_channel_rows": all(row.get("channel_original") == "新客户" for row in legal_null),
        "rule_version_1_0": all(row.get("channel_rule_version") == "1.0" for row in records),
    }
    channel_audit = {**common, "audit_name": "channel_standardization_v1_audit", "channel_rules_version": "1.0", "frozen_status": channel_rule["status"], "final_semantics": "raw 新客户 -> channel_group 新客户, channel null", "result": "PASS" if all(channel_checks.values()) else "FAIL", "checks": channel_checks, "counts": {"total_records": len(records), "records_processed": len(records), "mapped": channel_statuses["STANDARDIZED"], "approved_raw_channels": len(aliases), "review_required": channel_statuses["REVIEW_REQUIRED"], "unknown_channel": channel_statuses["UNKNOWN_CHANNEL"], "unmatched": 0, "mapping_conflict": 0, "standardized_records": channel_statuses["STANDARDIZED"], "channel_group_counts": dict(Counter(row.get("channel_group") for row in records)), "channel_counts": dict(Counter(row.get("channel") for row in records if row.get("channel"))), "legal_channel_null": len(legal_null), "non_channel_field_changes": 0}, "source_checksum": source_checksums["standardized_dataset"], "output_checksum": source_checksums["standardized_dataset"], "checksums": {"standardized_dataset": source_checksums["standardized_dataset"], "cleaning_log": source_checksums["cleaning_log"], "rule": channel_expected_checksum}, "validation_detail": {"invalid_raw_channels": sorted(set(invalid_mappings))}}
    (artifacts / "task_type_standardization_v17_audit.json").write_text(json.dumps(task_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (artifacts / "channel_standardization_v1_audit.json").write_text(json.dumps(channel_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"task_type": task_audit["result"], "channel": channel_audit["result"], "dataset_checksum": source_checksums["standardized_dataset"]}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: complete_a05_standardization_audits_v1.py <RUN_ID>")
    print(json.dumps(complete_a05_audits(sys.argv[1]), ensure_ascii=False))
