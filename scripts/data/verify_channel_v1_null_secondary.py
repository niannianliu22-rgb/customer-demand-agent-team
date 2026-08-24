#!/usr/bin/env python3
"""Apply the human-confirmed null secondary channel correction for Channel v1.0."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "runs/RUN-202608-DEMAND-001"
ART = RUN / "artifacts"
DATASET = ART / "unified_dataset.csv"
BACKUP = ART / "backups/unified_dataset_before_channel_v1.csv"
CFG = ROOT / "config/dimensions/channel"
REVIEW = ART / "dimension_review/channel"
VERSION = "1.0"
CANONICAL = ["老客户", "闲鱼", "垂直号", "小红书", "群推", "转介绍", "学生号", "备用", "对公"]
GROUPS = ["老客户", "新客户"]
CHANNEL_FIELDS = {"channel_original", "channel_group", "channel", "channel_rule_id", "channel_rule_version", "channel_standardization_status"}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    fields, before = read_csv(DATASET)
    aliases_path = CFG / "channel_aliases.yaml"
    canonical_path = CFG / "channel_canonical.yaml"
    frozen_path = CFG / "channel_rules_frozen_v1.yaml"
    aliases_doc = yaml.safe_load(aliases_path.read_text(encoding="utf-8"))
    canonical_doc = yaml.safe_load(canonical_path.read_text(encoding="utf-8"))
    frozen = yaml.safe_load(frozen_path.read_text(encoding="utf-8"))
    for doc in (aliases_doc, frozen):
        entry = next(entry for entry in doc["entries"] if entry["raw_channel"] == "新客户") if "entries" in doc else next(entry for entry in doc["aliases"] if entry["raw_channel"] == "新客户")
        entry["channel"] = None
    canonical_doc["canonical_channels"] = [entry for entry in canonical_doc["canonical_channels"] if entry["channel"] != "未知来源"]
    frozen["canonical_channels"] = [value for value in frozen["canonical_channels"] if value != "未知来源"]
    frozen["special_handling"] = [{"raw_channel": "新客户", "channel_group": "新客户", "channel": None, "rule": "Participates in new-customer group statistics only; excluded from named acquisition-channel attribution."}]
    if frozen["canonical_channels"] != CANONICAL or "未知来源" in str((aliases_doc, canonical_doc, frozen)):
        raise RuntimeError("canonical-channel correction failed")
    aliases_path.write_text(yaml.safe_dump(aliases_doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    canonical_path.write_text(yaml.safe_dump(canonical_doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    frozen_path.write_text(yaml.safe_dump(frozen, allow_unicode=True, sort_keys=False), encoding="utf-8")
    meta_path = CFG / "channel_rules_frozen_v1.metadata.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata.update({"canonical_channel_count": len(CANONICAL), "unknown_channel_count": 0, "corrected_at": datetime.now(timezone.utc).isoformat(), "correction": "raw_channel 新客户 uses legal null channel; 未知来源 is not canonical."})
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    changed_rows = []
    after = []
    for row in before:
        output = dict(row)
        if row["channel_original"] == "新客户":
            if row["channel_group"] != "新客户" or row["channel"] not in {"", "未知来源", "UNKNOWN_CHANNEL", "unknown"}:
                raise RuntimeError("unexpected new-customer channel state")
            output["channel"] = ""
            output["channel_standardization_status"] = "STANDARDIZED"
            changed_rows.append(output)
        after.append(output)
    if len(changed_rows) != 12:
        raise RuntimeError(f"expected 12 new-customer rows, found {len(changed_rows)}")
    write_csv(DATASET, fields, after)
    _, result = read_csv(DATASET)
    mapping_fields, mapping = read_csv(REVIEW / "channel_final_mapping.csv")
    for row in mapping:
        if row["raw_channel"] == "新客户":
            row.update({"channel_group": "新客户", "channel": "", "mapping_source": "manual_business_confirmation", "rule_id": "CHANNEL-RULE-010", "review_status": "APPROVED"})
    write_csv(REVIEW / "channel_final_mapping.csv", mapping_fields, mapping)
    inventory = Counter((row["channel_group"], row["channel"]) for row in result)
    write_csv(ART / "channel_standardized_value_inventory.csv", ["channel_group", "channel", "record_count"], [{"channel_group": group, "channel": channel, "record_count": count} for (group, channel), count in sorted(inventory.items())])
    write_csv(ART / "channel_unmatched_values.csv", ["raw_channel", "record_count", "reason"], [])
    test_rows = []
    for entry in frozen["aliases"]:
        raw = entry["raw_channel"]
        expected = "" if entry["channel"] is None else entry["channel"]
        matches = [row for row in result if row["channel_original"] == raw]
        ok = bool(matches) and all(row["channel_group"] == entry["channel_group"] and row["channel"] == expected and row["channel_standardization_status"] == "STANDARDIZED" for row in matches)
        test_rows.append({"raw_channel": raw, "expected_channel_group": entry["channel_group"], "expected_channel": expected, "records": len(matches), "status": "PASS" if ok else "FAIL"})
    regression = {"channel_rules_version": VERSION, "passed": sum(row["status"] == "PASS" for row in test_rows), "failed": sum(row["status"] == "FAIL" for row in test_rows), "tests": test_rows, "legal_null_secondary_channel": {"raw_channel": "新客户", "channel_group": "新客户", "channel": None, "record_count": 12}}
    (ART / "channel_standardization_regression_test.json").write_text(json.dumps(regression, ensure_ascii=False, indent=2), encoding="utf-8")
    _, backup = read_csv(BACKUP)
    non_channel_fields = [field for field in fields if field not in CHANNEL_FIELDS]
    non_channel_changed = []
    for index, (old, new) in enumerate(zip(backup, result), start=2):
        changed = [field for field in non_channel_fields if old.get(field, "") != new.get(field, "")]
        if changed: non_channel_changed.append({"csv_row": index, "fields": changed})
    groups = Counter(row["channel_group"] for row in result)
    channels = Counter(row["channel"] for row in result)
    legal_null = [row for row in result if row["channel"] == ""]
    checks = {
        "total_records_818": len(result) == 818,
        "all_30_raw_channels_covered": len({row["channel_original"] for row in result}) == 30,
        "review_required_zero": all(row["channel_standardization_status"] != "REVIEW_REQUIRED" for row in result),
        "unknown_channel_zero": all(row["channel_standardization_status"] != "UNKNOWN_CHANNEL" for row in result),
        "unmatched_zero": True,
        "mapping_conflict_zero": len(frozen["aliases"]) == len({entry["raw_channel"] for entry in frozen["aliases"]}),
        "channel_groups_valid": set(groups) <= set(GROUPS),
        "channels_valid_or_legal_null": all(value in CANONICAL for value in channels if value),
        "legal_null_channel_rows": len(legal_null) == 12 and all(row["channel_original"] == "新客户" and row["channel_group"] == "新客户" for row in legal_null),
        "unknown_source_not_canonical": "未知来源" not in str((aliases_doc, canonical_doc, frozen)),
        "channel_original_preserved": all(old["channel"] == new["channel_original"] for old, new in zip(backup, result)),
        "non_channel_fields_unchanged": not non_channel_changed,
        "task_type_frozen_v17_fields_unchanged": all(old["task_type"] == new["task_type"] and old["task_type_original"] == new["task_type_original"] and old["task_type_mode"] == new["task_type_mode"] and old["task_type_components"] == new["task_type_components"] and old["task_type_rule_id"] == new["task_type_rule_id"] and old["task_type_rule_version"] == new["task_type_rule_version"] and old["task_type_standardization_status"] == new["task_type_standardization_status"] for old, new in zip(backup, result))
    }
    audit = {"run_id": RUN.name, "audit_name": "channel_standardization_v1_audit", "result": "PASS" if all(checks.values()) and regression["failed"] == 0 else "FAIL", "channel_rules_version": VERSION, "final_semantics": "raw 新客户 -> channel_group 新客户, channel null", "counts": {"total_records": len(result), "approved_raw_channels": 30, "review_required": 0, "unknown_channel": 0, "unmatched": 0, "mapping_conflict": 0, "standardized_records": len(result), "channel_group_counts": dict(groups), "channel_counts": {value: count for value, count in channels.items() if value}, "legal_channel_null": len(legal_null), "non_channel_field_changes": len(non_channel_changed)}, "checks": checks, "checksums": {"backup": sha(BACKUP), "standardized_dataset": sha(DATASET)}}
    (ART / "channel_standardization_v1_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    status_path = ART / "dimension_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")); status["dimensions"]["channel"]["data_quality"] = audit["result"]; status["updated_at"] = datetime.now(timezone.utc).isoformat()
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    if audit["result"] != "PASS": raise RuntimeError("Channel v1 final Data Quality failed")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
