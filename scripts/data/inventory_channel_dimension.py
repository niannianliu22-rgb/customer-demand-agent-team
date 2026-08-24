#!/usr/bin/env python3
"""Read-only discovery inventory for the channel dimension; creates review artifacts only."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "runs/RUN-202608-DEMAND-001"
ART = RUN / "artifacts"
DATASET = ART / "unified_dataset.csv"
OUT = ART / "dimension_review/channel"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def amount(value):
    try:
        return Decimal(value) if value.strip() else Decimal("0")
    except (InvalidOperation, AttributeError):
        return Decimal("0")


def compact_distribution(counter):
    return json.dumps(dict(sorted(counter.items())), ensure_ascii=False, separators=(",", ":"))


def value_notes(raw):
    notes = []
    if raw != raw.strip():
        notes.append("leading_or_trailing_whitespace")
    if any(char.isspace() for char in raw):
        notes.append("contains_internal_whitespace")
    if any(separator in raw for separator in ("-", "－", "+", "＋", "/", "、", "，", ",")):
        notes.append("contains_separator; may be composite or hierarchical; human confirmation required")
    if len(raw) == 1 and raw.isascii() and raw.isalpha():
        notes.append("opaque_single_letter_label; business meaning not inferred")
    if raw.endswith("类") or "客户" in raw:
        notes.append("contains_customer_or_class_marker; not assumed to be a channel")
    return "; ".join(notes)


def main():
    rows = read_csv(DATASET)
    OUT.mkdir(parents=True, exist_ok=True)
    buckets = defaultdict(list)
    for row in rows:
        buckets[row.get("channel", "")].append(row)
    inventory = []
    for raw, bucket in sorted(buckets.items(), key=lambda item: (-len(item[1]), item[0])):
        years = Counter(row["year"] for row in bucket)
        departments = Counter(row["department"] for row in bucket)
        total = sum((amount(row.get("amount_cny", "")) for row in bucket), Decimal("0"))
        inventory.append({
            "raw_channel": raw,
            "record_count": len(bucket),
            "year_distribution": compact_distribution(years),
            "department_distribution": compact_distribution(departments),
            "amount_cny_sum": format(total.quantize(Decimal("0.01")), "f"),
            "notes": value_notes(raw),
        })
    write_csv(OUT / "channel_raw_value_inventory.csv", ["raw_channel", "record_count", "year_distribution", "department_distribution", "amount_cny_sum", "notes"], inventory)
    candidates = [{
        "raw_channel": item["raw_channel"],
        "record_count": item["record_count"],
        "candidate_canonical_channel": "",
        "confidence": "",
        "reason": "Discovery only: no value-level channel rule or human approval is applied.",
        "review_status": "REVIEW_REQUIRED",
    } for item in inventory]
    write_csv(OUT / "channel_candidate_mapping.csv", ["raw_channel", "record_count", "candidate_canonical_channel", "confidence", "reason", "review_status"], candidates)
    mapping = json.loads((ART / "schema_mapping.json").read_text(encoding="utf-8"))
    lineage = []
    for item in mapping["items"]:
        if item.get("canonical_field") == "channel":
            lineage.append({"source_id": item["source_id"], "raw_field_name": item["raw_field_name"], "mapping_status": item["status"], "rule_id": "RULE-007"})
    profiles = []
    terms = ("channel", "客户来源", "客户类型", "来源", "渠道", "咨询来源", "获客渠道")
    for path in sorted((ART / "source_profiles").glob("source_*.json")):
        profile = json.loads(path.read_text(encoding="utf-8"))
        matches = []
        for sheet_name, sheet in profile["sheets"].items():
            for field in sheet["fields"]:
                if any(term.lower() in field["field_name"].lower() for term in terms):
                    matches.append(field["field_name"])
        profiles.append({"source_id": profile["source_id"], "source_profile": str(path.relative_to(ROOT)), "matching_raw_fields": matches})
    lexical_groups = [
        {"signal": "shared_lexical_prefix_only", "values": ["老客户", "老客户A类", "老客户B类", "老客户B-"], "interpretation": "Shared text only; not a merge recommendation."},
        {"signal": "shared_lexical_prefix_only", "values": ["群推", "群推优质", "群推不优质"], "interpretation": "Shared text only; qualifier handling requires human decision."},
        {"signal": "shared_lexical_token_and_separator", "values": ["转介绍", "转介绍-老客户", "转介绍-备用", "转介绍-垂直号", "备用-转介绍"], "interpretation": "Contains standalone and compound forms; direction and aggregation meaning are unconfirmed."},
        {"signal": "opaque_label_and_expanded_label", "values": ["A", "A类客户", "B", "B类客户"], "interpretation": "Surface resemblance only; label semantics are unconfirmed."},
    ]
    conflicts = [
        {"type": "taxonomy_scope", "evidence": ["老客户", "新客户", "老客户A类", "老客户B类", "A类客户", "B类客户", "A", "B", "C", "D", "E"], "reason": "The data mix contains customer-status/class-like labels and source-like labels. No rule authorizes treating them as the same taxonomy."},
        {"type": "compound_value_semantics", "evidence": [item["raw_channel"] for item in inventory if "contains_separator" in item["notes"]], "reason": "Separator-bearing values may encode multiple labels, hierarchy, or a literal name; no decomposition rule exists."},
        {"type": "opaque_label_semantics", "evidence": [item["raw_channel"] for item in inventory if "opaque_single_letter_label" in item["notes"]], "reason": "Single-letter labels have no documented business meaning."},
        {"type": "field_lineage_vs_value_taxonomy", "evidence": ["RULE-007"], "reason": "RULE-007 confirms field equivalence only; it does not provide a channel value taxonomy, aliases, or value-level standardization instructions."},
    ]
    rules_found = [{"rule_id": "RULE-007", "status": "ACTIVE", "scope": "schema_mapping_agent", "effect": "Field-level equivalence only: 客户来源 / 客户类型 -> channel; no value-level aliases or canonical list."}]
    report = {
        "run_id": RUN.name,
        "dimension": "channel",
        "phase": "INVENTORY_DISCOVERY_ONLY",
        "total_records": len(rows),
        "non_null_records": sum(bool(row.get("channel", "")) for row in rows),
        "null_records": sum(not bool(row.get("channel", "")) for row in rows),
        "unique_raw_values": len(buckets),
        "suspected_alias_groups": lexical_groups,
        "suspected_business_conflicts": conflicts,
        "existing_rules_found": rules_found,
        "existing_channel_aliases_or_canonical_list": [],
        "historical_channel_standardization": {"value_level_script_or_artifact_found": False, "current_value_changed_by_prior_process": False, "evidence": "channel is identical row-by-row in the pre-school-standardization and pre-task-type-v17 backups."},
        "lineage_summary": {"confirmed_by_rule": "RULE-007", "schema_mapping": lineage, "source_profile_field_scan": profiles, "near_synonyms_not_found_in_source_profiles": ["channel", "来源", "渠道", "咨询来源", "获客渠道"]},
        "constraints": ["No channel mapping was approved.", "All candidate rows are REVIEW_REQUIRED.", "No Frozen channel rules were created.", "unified_dataset.csv was read only."],
    }
    (OUT / "channel_dimension_inventory.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"total_records": report["total_records"], "non_null_records": report["non_null_records"], "null_records": report["null_records"], "unique_raw_values": report["unique_raw_values"], "output": str(OUT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
