#!/usr/bin/env python3
"""Exact-match coverage audit for the human-confirmed Channel v1 instruction.

This script intentionally does not standardize data, mutate schemas, or emit rules.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "runs/RUN-202608-DEMAND-001"
ART = RUN / "artifacts"
OUT = ART / "dimension_review/channel"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    rows = read_csv(ART / "unified_dataset.csv")
    values = Counter(row["channel"] for row in rows)
    confirmed = {}
    def add(raw_values, group, channel, rule_id):
        for raw in raw_values:
            if raw in confirmed and confirmed[raw] != (group, channel, rule_id):
                raise RuntimeError(f"conflicting exact instruction mapping for {raw!r}")
            confirmed[raw] = (group, channel, rule_id)
    add(["老客户", "老客户A类", "老客户B类", "A类客户", "B类客户", "A", "B"], "老客户", "老客户", "MANUAL-CHANNEL-V1-001")
    add(["闲鱼"], "新客户", "闲鱼", "MANUAL-CHANNEL-V1-002")
    add(["垂直号"], "新客户", "垂直号", "MANUAL-CHANNEL-V1-003")
    add(["小红书"], "新客户", "小红书", "MANUAL-CHANNEL-V1-004")
    add(["群推", "群推优质", "群推不优质"], "新客户", "群推", "MANUAL-CHANNEL-V1-005")
    add(["转介绍", "转介绍-老客户", "转介绍-备用", "转介绍-垂直号"], "新客户", "转介绍", "MANUAL-CHANNEL-V1-006")
    add(["学生号"], "新客户", "学生号", "MANUAL-CHANNEL-V1-007")
    add(["备用客户", "C", "D", "E", "备用-垂直号", "备用-转介绍", "备用-推广", "备用-学生号", "备用-小红书"], "新客户", "备用", "MANUAL-CHANNEL-V1-008")
    # Deliberately exact: the instruction says 渠道-B端, while the dataset has 渠道- B端.
    add(["渠道-B端"], "新客户", "对公", "MANUAL-CHANNEL-V1-009")
    mappings = []
    conflict_count = 0
    for raw, count in sorted(values.items(), key=lambda item: (-item[1], item[0])):
        if raw in confirmed:
            group, channel, rule_id = confirmed[raw]
            mappings.append({"raw_channel": raw, "record_count": count, "channel_group": group, "channel": channel, "mapping_source": "manual_business_confirmation", "rule_id": rule_id, "review_status": "APPROVED"})
        elif raw == "新客户":
            mappings.append({"raw_channel": raw, "record_count": count, "channel_group": "新客户", "channel": "UNKNOWN_CHANNEL", "mapping_source": "manual_business_confirmation", "rule_id": "MANUAL-CHANNEL-V1-UNKNOWN", "review_status": "UNKNOWN_CHANNEL"})
        else:
            mappings.append({"raw_channel": raw, "record_count": count, "channel_group": "", "channel": "", "mapping_source": "", "rule_id": "", "review_status": "REVIEW_REQUIRED"})
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "channel_final_mapping.csv", ["raw_channel", "record_count", "channel_group", "channel", "mapping_source", "rule_id", "review_status"], mappings)
    schema = json.loads((ROOT / "schemas/canonical_schema.json").read_text(encoding="utf-8"))
    fields = [field["name"] for field in schema["fields"]]
    schema_audit = {
        "audit_name": "channel_schema_compatibility_audit",
        "run_id": RUN.name,
        "current_schema_version": schema["schema_version"],
        "current_schema_status": schema["status"],
        "existing_channel_fields": [field for field in fields if field.startswith("channel")],
        "requested_channel_fields": ["channel_original", "channel_group", "channel"],
        "compatibility": "REQUIRES_SCHEMA_VERSION_UPGRADE",
        "proposed_schema_version": "1.2.0",
        "field_conflicts": [],
        "proposed_change": "Add channel_original and channel_group; retain channel as the existing canonical secondary-channel field.",
        "application_status": "NOT_APPLIED",
        "reason_not_applied": "Channel v1 publication is blocked by unresolved exact raw values and UNKNOWN_CHANNEL secondary-channel value; no dataset standardization may proceed."
    }
    (OUT / "channel_schema_compatibility_audit.json").write_text(json.dumps(schema_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = Counter(row["review_status"] for row in mappings)
    record_counts = Counter()
    for row in mappings:
        record_counts[row["review_status"]] += int(row["record_count"])
    audit = {
        "audit_name": "channel_v1_exact_coverage_audit",
        "run_id": RUN.name,
        "total_raw_channels": len(values),
        "total_records": len(rows),
        "raw_status_counts": dict(counts),
        "record_status_counts": dict(record_counts),
        "approved_raw_channels": counts["APPROVED"],
        "review_required_raw_channels": counts["REVIEW_REQUIRED"],
        "unknown_channel_raw_channels": counts["UNKNOWN_CHANNEL"],
        "mapping_conflict_count": conflict_count,
        "publication_status": "BLOCKED",
        "blockers": [
            {"raw_channel": "老客户B-", "record_count": values["老客户B-"], "reason": "Not included in the explicit human-confirmed mapping list."},
            {"raw_channel": "渠道- B端", "record_count": values["渠道- B端"], "reason": "Does not exactly match the confirmed value 渠道-B端; whitespace normalization was not authorized."},
            {"raw_channel": "新客户", "record_count": values["新客户"], "reason": "Confirmed as channel_group=新客户, but no secondary channel is confirmed; retained as UNKNOWN_CHANNEL."}
        ],
        "not_generated": [
            "config/dimensions/channel/channel_aliases.yaml",
            "config/dimensions/channel/channel_canonical.yaml",
            "config/dimensions/channel/channel_rules_frozen_v1.yaml",
            "config/dimensions/channel/channel_rules_frozen_v1.metadata.json",
            "channel_standardization_v1_audit.json",
            "channel_standardization_regression_test.json",
            "channel_standardized_value_inventory.csv",
            "channel_unmatched_values.csv"
        ],
        "dataset_modified": False,
        "task_type_modified": False
    }
    (OUT / "channel_v1_exact_coverage_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
