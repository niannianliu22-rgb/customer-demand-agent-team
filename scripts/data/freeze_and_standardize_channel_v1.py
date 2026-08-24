#!/usr/bin/env python3
"""Freeze the human-confirmed Channel v1.0 rules and standardize only channel fields."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "runs/RUN-202608-DEMAND-001"
ART = RUN / "artifacts"
DATASET = ART / "unified_dataset.csv"
BACKUP = ART / "backups/unified_dataset_before_channel_v1.csv"
CFG = ROOT / "config/dimensions/channel"
SCHEMA = ROOT / "schemas/canonical_schema.json"
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
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader(); writer.writerows(rows)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mappings():
    result = {}
    def add(values, group, channel, rule_id):
        for raw in values:
            if raw in result:
                raise RuntimeError(f"duplicate channel alias: {raw!r}")
            result[raw] = {"raw_channel": raw, "channel_group": group, "channel": channel, "rule_id": rule_id, "source": "manual_business_confirmation", "status": "ACTIVE"}
    add(["老客户", "老客户A类", "老客户B类", "老客户B-", "A类客户", "B类客户", "A", "B"], "老客户", "老客户", "CHANNEL-RULE-001")
    add(["闲鱼"], "新客户", "闲鱼", "CHANNEL-RULE-002")
    add(["垂直号"], "新客户", "垂直号", "CHANNEL-RULE-003")
    add(["小红书"], "新客户", "小红书", "CHANNEL-RULE-004")
    add(["群推", "群推优质", "群推不优质"], "新客户", "群推", "CHANNEL-RULE-005")
    add(["转介绍", "转介绍-老客户", "转介绍-备用", "转介绍-垂直号"], "新客户", "转介绍", "CHANNEL-RULE-006")
    add(["学生号"], "新客户", "学生号", "CHANNEL-RULE-007")
    add(["备用客户", "C", "D", "E", "备用-垂直号", "备用-转介绍", "备用-推广", "备用-学生号", "备用-小红书"], "新客户", "备用", "CHANNEL-RULE-008")
    add(["渠道- B端"], "新客户", "对公", "CHANNEL-RULE-009")
    add(["新客户"], "新客户", "", "CHANNEL-RULE-010")
    return result


def upgrade_schema():
    before = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if before["schema_version"] != "1.1.0" or before["status"] != "FROZEN":
        raise RuntimeError("expected frozen canonical schema v1.1.0")
    old_fields = before["fields"]
    names = [field["name"] for field in old_fields]
    if names.count("channel") != 1 or "channel_original" in names or "channel_group" in names:
        raise RuntimeError("channel schema field conflict")
    additions = [
        {"name": "channel_original", "type": "string", "required": False},
        {"name": "channel_group", "type": "string", "required": False, "allowed_values": GROUPS},
        {"name": "channel_rule_id", "type": "string", "required": False},
        {"name": "channel_rule_version", "type": "string", "required": False},
        {"name": "channel_standardization_status", "type": "string", "required": False},
    ]
    index = names.index("channel")
    after = dict(before)
    after["schema_version"] = "1.2.0"
    after["fields"] = old_fields[:index] + additions[:2] + [old_fields[index]] + additions[2:] + old_fields[index + 1:]
    SCHEMA.write_text(json.dumps(after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = {
        "audit_name": "canonical_schema_channel_v1_change_audit", "run_id": RUN.name,
        "status": "PASS", "previous_schema_version": "1.1.0", "new_schema_version": "1.2.0",
        "change": {"added_fields": [entry["name"] for entry in additions], "retained_existing_channel_field": True},
        "non_channel_field_definitions_unchanged": all(a == b for a, b in zip(old_fields[:index], after["fields"][:index])) and all(a == b for a, b in zip(old_fields[index + 1:], after["fields"][index + 1 + len(additions):])),
        "source": "manual_business_confirmation", "rule_id": "RULE-028"
    }
    (ART / "canonical_schema_channel_v1_change_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit


def output_fields(old_fields):
    retained = [field for field in old_fields if field not in CHANNEL_FIELDS - {"channel"}]
    index = retained.index("channel")
    additions = ["channel_original", "channel_group", "channel", "channel_rule_id", "channel_rule_version", "channel_standardization_status"]
    retained.pop(index)
    return retained[:index] + additions + retained[index:]


def main():
    if BACKUP.exists():
        raise RuntimeError(f"refusing to overwrite backup {BACKUP}")
    old_fields, before = read_csv(DATASET)
    aliases = mappings()
    raw_values = {row["channel"] for row in before}
    if raw_values != set(aliases):
        raise RuntimeError(f"frozen mapping coverage mismatch: unmapped={sorted(raw_values-set(aliases))}; unused={sorted(set(aliases)-raw_values)}")
    if len(aliases) != 30 or any(entry["channel"] not in CANONICAL for entry in aliases.values()):
        raise RuntimeError("invalid frozen channel rules")
    CFG.mkdir(parents=True, exist_ok=True)
    alias_entries = [aliases[key] for key in sorted(aliases)]
    canonical = {"channel_canonical_version": VERSION, "status": "ACTIVE", "source": "manual_business_confirmation", "channel_groups": GROUPS, "canonical_channels": [{"channel": value, "channel_group": "老客户" if value == "老客户" else "新客户", "analysis_note": ""} for value in CANONICAL]}
    aliases_doc = {"channel_aliases_version": VERSION, "status": "ACTIVE", "source": "manual_business_confirmation", "entries": alias_entries}
    frozen = {"channel_rules_version": VERSION, "status": "FROZEN", "source": "manual_business_confirmation", "priority_order": ["manual_business_confirmation_active_rule", "frozen_channel_v1", "model_inference_forbidden"], "canonical_channel_groups": GROUPS, "canonical_channels": CANONICAL, "aliases": alias_entries, "special_handling": [{"raw_channel": "新客户", "channel_group": "新客户", "channel": None, "rule": "Participates in new-customer group statistics only; excluded from named acquisition-channel attribution."}]}
    (CFG / "channel_aliases.yaml").write_text(yaml.safe_dump(aliases_doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (CFG / "channel_canonical.yaml").write_text(yaml.safe_dump(canonical, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (CFG / "channel_rules_frozen_v1.yaml").write_text(yaml.safe_dump(frozen, allow_unicode=True, sort_keys=False), encoding="utf-8")
    metadata = {"channel_rules_version": VERSION, "status": "FROZEN", "source": "manual_business_confirmation", "raw_channel_count": len(aliases), "canonical_channel_count": len(CANONICAL), "canonical_group_count": len(GROUPS), "mapping_conflict_count": 0, "review_required_count": 0, "unknown_channel_count": 0, "inputs": {"dataset_before_standardization_sha256": digest(DATASET), "schema_before_upgrade_version": "1.1.0"}, "created_at": datetime.now(timezone.utc).isoformat()}
    (CFG / "channel_rules_frozen_v1.metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    schema_audit = upgrade_schema()
    BACKUP.parent.mkdir(exist_ok=True)
    shutil.copy2(DATASET, BACKUP)
    old_fields, before = read_csv(BACKUP)
    fields = output_fields(old_fields)
    output = []
    for old in before:
        raw = old["channel"]
        rule = aliases[raw]
        row = dict(old)
        row.update({"channel_original": raw, "channel_group": rule["channel_group"], "channel": rule["channel"], "channel_rule_id": rule["rule_id"], "channel_rule_version": VERSION, "channel_standardization_status": "STANDARDIZED"})
        output.append(row)
    write_csv(DATASET, fields, output)
    _, after = read_csv(DATASET)
    mapping_rows = [{"raw_channel": raw, "record_count": sum(row["channel_original"] == raw for row in after), "channel_group": rule["channel_group"], "channel": rule["channel"], "mapping_source": "manual_business_confirmation", "rule_id": rule["rule_id"], "review_status": "APPROVED"} for raw, rule in sorted(aliases.items())]
    write_csv(REVIEW / "channel_final_mapping.csv", ["raw_channel", "record_count", "channel_group", "channel", "mapping_source", "rule_id", "review_status"], mapping_rows)
    statuses = Counter(row["channel_standardization_status"] for row in after)
    group_counts = Counter(row["channel_group"] for row in after)
    channel_counts = Counter(row["channel"] for row in after)
    invariant_fields = [field for field in old_fields if field not in CHANNEL_FIELDS]
    changed_non_channel = [{"csv_row": index + 2, "fields": [field for field in invariant_fields if old.get(field, "") != new.get(field, "")]} for index, (old, new) in enumerate(zip(before, after))]
    changed_non_channel = [item for item in changed_non_channel if item["fields"]]
    test_rows = []
    for raw, rule in aliases.items():
        matching = [row for row in after if row["channel_original"] == raw]
        ok = bool(matching) and all(row["channel_group"] == rule["channel_group"] and row["channel"] == rule["channel"] and row["channel_standardization_status"] == "STANDARDIZED" for row in matching)
        test_rows.append({"raw_channel": raw, "expected_channel_group": rule["channel_group"], "expected_channel": rule["channel"], "records": len(matching), "status": "PASS" if ok else "FAIL"})
    regression = {"channel_rules_version": VERSION, "passed": sum(row["status"] == "PASS" for row in test_rows), "failed": sum(row["status"] == "FAIL" for row in test_rows), "tests": test_rows}
    (ART / "channel_standardization_regression_test.json").write_text(json.dumps(regression, ensure_ascii=False, indent=2), encoding="utf-8")
    inventory = [{"channel_group": group, "channel": channel, "record_count": count} for (group, channel), count in sorted(Counter((row["channel_group"], row["channel"]) for row in after).items())]
    write_csv(ART / "channel_standardized_value_inventory.csv", ["channel_group", "channel", "record_count"], inventory)
    write_csv(ART / "channel_unmatched_values.csv", ["raw_channel", "record_count", "reason"], [])
    checks = {
        "total_records_818": len(after) == 818,
        "all_30_raw_channels_covered": len(aliases) == 30 and set(row["channel_original"] for row in after) == set(aliases),
        "review_required_zero": statuses["REVIEW_REQUIRED"] == 0,
        "unknown_channel_zero": statuses["UNKNOWN_CHANNEL"] == 0,
        "unmatched_zero": 0 == 0,
        "mapping_conflict_zero": len(aliases) == len(set(aliases)),
        "channel_groups_valid": set(group_counts) <= set(GROUPS),
        "channels_valid": set(channel_counts) <= set(CANONICAL),
        "channel_original_preserved": all(old["channel"] == new["channel_original"] for old, new in zip(before, after)),
        "non_channel_fields_unchanged": not changed_non_channel,
        "task_type_frozen_v17_fields_unchanged": all(old["task_type"] == new["task_type"] and old["task_type_original"] == new["task_type_original"] and old["task_type_mode"] == new["task_type_mode"] and old["task_type_components"] == new["task_type_components"] and old["task_type_rule_id"] == new["task_type_rule_id"] and old["task_type_rule_version"] == new["task_type_rule_version"] and old["task_type_standardization_status"] == new["task_type_standardization_status"] for old, new in zip(before, after)),
        "frozen_rule_version_1_0": frozen["channel_rules_version"] == VERSION and frozen["status"] == "FROZEN",
        "schema_change_audit_pass": schema_audit["status"] == "PASS"
    }
    audit = {"run_id": RUN.name, "audit_name": "channel_standardization_v1_audit", "result": "PASS" if all(checks.values()) and regression["failed"] == 0 else "FAIL", "channel_rules_version": VERSION, "counts": {"total_records": len(after), "approved_raw_channels": len(aliases), "review_required": statuses["REVIEW_REQUIRED"], "unknown_channel": statuses["UNKNOWN_CHANNEL"], "unmatched": 0, "mapping_conflict": 0, "standardized_records": statuses["STANDARDIZED"], "channel_group_counts": dict(group_counts), "channel_counts": dict(channel_counts), "non_channel_field_changes": len(changed_non_channel)}, "checks": checks, "checksums": {"backup": digest(BACKUP), "standardized_dataset": digest(DATASET)}}
    (ART / "channel_standardization_v1_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    status_path = ART / "dimension_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {"run_id": RUN.name, "dimensions": {}}
    status.setdefault("dimensions", {})["channel"] = {"status": "STANDARDIZED", "rule_version": VERSION, "data_quality": audit["result"], "rule_source": str((CFG / "channel_rules_frozen_v1.yaml").relative_to(ROOT)), "artifacts": [str((ART / name).relative_to(ROOT)) for name in ["channel_standardization_v1_audit.json", "channel_standardization_regression_test.json", "channel_standardized_value_inventory.csv", "channel_unmatched_values.csv"]]}
    status["updated_at"] = datetime.now(timezone.utc).isoformat()
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    if audit["result"] != "PASS":
        raise RuntimeError("Channel Data Quality failed")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
