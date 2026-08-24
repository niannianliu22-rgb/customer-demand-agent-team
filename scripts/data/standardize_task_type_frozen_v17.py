#!/usr/bin/env python3
"""Apply the already-frozen Task Type v17.0 rules without reclassification."""
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
BACKUP = ART / "backups/unified_dataset_before_task_type_v17.csv"
RULES = ROOT / "config/dimensions/task_type/task_type_rules_frozen_v17.yaml"
VERSION = "17.0"
TASK_FIELDS = {
    "task_type", "task_type_original", "task_type_mode", "task_type_components",
    "task_type_rule_id", "task_type_rule_version", "task_type_standardization_status",
}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def task_fields(fields):
    additions = [
        "task_type_original", "task_type_mode", "task_type_components",
        "task_type_rule_id", "task_type_rule_version", "task_type_standardization_status",
    ]
    retained = [field for field in fields if field not in TASK_FIELDS - {"task_type"}]
    index = retained.index("task_type") + 1
    return retained[:index] + additions + retained[index:]


def build_lookups(rules):
    official = set(rules["official_task_types"])
    aliases = {entry["raw_value"]: entry for entry in rules["aliases"]}
    multi = {entry["raw_value"]: entry for entry in rules["multi_task_rules"]}
    excluded = {entry["raw_value"]: entry for entry in rules["excluded_values"]}
    unknown = {entry["raw_value"]: entry for entry in rules["unknown_values"]}
    active = {entry["rule_id"] for entry in rules["aliases"]} | {entry["rule_id"] for entry in rules["multi_task_rules"]}
    deprecated = {entry["rule_id"] for entry in rules.get("deprecated_rules", [])}
    if rules.get("status") != "FROZEN" or rules.get("task_type_rules_version") != VERSION:
        raise RuntimeError("Frozen v17.0 rule set is not valid for execution")
    if active & deprecated:
        raise RuntimeError("Deprecated rule leakage in frozen rule set")
    return official, aliases, multi, excluded, unknown, deprecated


def classify(raw, official, aliases, multi, excluded, unknown):
    if raw in multi:
        rule = multi[raw]
        return ("MULTI_TASK", "MULTI_TASK", "MULTI_TASK", rule["task_type_components"], rule["rule_id"])
    if raw in aliases:
        rule = aliases[raw]
        return ("STANDARDIZED", rule["official_task_type"], "SINGLE_TASK", [], rule["rule_id"])
    if raw in excluded:
        return ("EXCLUDED_BY_BUSINESS_RULE", "", "EXCLUDED", [], "RULE-027")
    if raw in unknown:
        return ("UNKNOWN", "UNKNOWN", "UNKNOWN", [], "NO_INFERENCE")
    if raw in official:
        return ("STANDARDIZED", raw, "SINGLE_TASK", [], "CANONICAL_IDENTITY")
    return ("UNMATCHED", "UNKNOWN", "UNKNOWN", [], "NO_FROZEN_RULE_MATCH")


def validate(before_fields, before, after_fields, after, rules, official, deprecated):
    errors = []
    checks = {}
    def check(name, condition, detail):
        checks[name] = {"pass": bool(condition), "detail": detail}
        if not condition:
            errors.append(name)

    check("total_record_count_unchanged", len(before) == len(after), {"before": len(before), "after": len(after)})
    check("task_type_original_preserved", all(row.get("task_type_original") == original.get("task_type", "") for original, row in zip(before, after)), {"checked_rows": len(after)})
    formal = [row["task_type"] for row in after if row["task_type_standardization_status"] == "STANDARDIZED"]
    check("formal_task_types_are_canonical", all(value in official for value in formal), {"formal_rows": len(formal), "invalid": sorted(set(formal) - official)})
    multi_invalid = []
    for row in after:
        if row["task_type_standardization_status"] == "MULTI_TASK":
            try:
                components = json.loads(row["task_type_components"])
            except json.JSONDecodeError:
                components = []
            if not components or any(component not in official for component in components):
                multi_invalid.append(row["task_type_original"])
    check("multi_task_components_are_canonical", not multi_invalid, {"invalid_raw_values": sorted(set(multi_invalid))})
    statuses = Counter(row["task_type_standardization_status"] for row in after)
    check("review_required_zero", statuses["REVIEW_REQUIRED"] == 0, {"count": statuses["REVIEW_REQUIRED"]})
    check("proposed_medium_zero", statuses["PROPOSED_MEDIUM"] == 0, {"count": statuses["PROPOSED_MEDIUM"]})
    check("proposed_high_zero", statuses["PROPOSED_HIGH"] == 0, {"count": statuses["PROPOSED_HIGH"]})
    leakage = [row["task_type_rule_id"] for row in after if row["task_type_rule_id"] in deprecated]
    check("deprecated_leakage_zero", not leakage, {"rule_ids": sorted(set(leakage)), "count": len(leakage)})
    invariant_fields = [field for field in before_fields if field not in TASK_FIELDS]
    changed_non_task = []
    for number, (original, row) in enumerate(zip(before, after), start=2):
        changed = [field for field in invariant_fields if original.get(field, "") != row.get(field, "")]
        if changed:
            changed_non_task.append({"csv_row": number, "fields": changed})
    check("non_task_type_fields_rowwise_unchanged", not changed_non_task, {"changed_rows": len(changed_non_task), "examples": changed_non_task[:10]})
    unmatched = [row for row in after if row["task_type_standardization_status"] == "UNMATCHED"]
    check("unmatched_explicitly_counted", True, {"count": len(unmatched)})
    return checks, errors, statuses, unmatched, changed_non_task


def main():
    rules = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    official, aliases, multi, excluded, unknown, deprecated = build_lookups(rules)
    if not DATASET.is_file():
        raise RuntimeError("unified_dataset.csv is missing")
    if BACKUP.exists():
        raise RuntimeError(f"Refusing to overwrite existing backup: {BACKUP}")
    BACKUP.parent.mkdir(exist_ok=True)
    shutil.copy2(DATASET, BACKUP)
    before_fields, before = read_csv(BACKUP)
    fields = task_fields(before_fields)
    output, unmatched = [], defaultdict(list)
    for original in before:
        raw = original.get("task_type", "")
        status, value, mode, components, rule_id = classify(raw, official, aliases, multi, excluded, unknown)
        row = {field: original.get(field, "") for field in before_fields}
        row.update({
            "task_type": value,
            "task_type_original": raw,
            "task_type_mode": mode,
            "task_type_components": json.dumps(components, ensure_ascii=False),
            "task_type_rule_id": rule_id,
            "task_type_rule_version": VERSION,
            "task_type_standardization_status": status,
        })
        if status == "UNMATCHED":
            unmatched[raw].append(row)
        output.append(row)
    write_csv(DATASET, fields, output)
    after_fields, after = read_csv(DATASET)
    checks, errors, statuses, unmatched_rows, changed_non_task = validate(before_fields, before, after_fields, after, rules, official, deprecated)
    unmatched_csv = [{"original_value": raw, "count": len(rows), "source_ids": "|".join(sorted({row["source_id"] for row in rows})), "reason": "No frozen v17 rule matched; no inference performed."} for raw, rows in sorted(unmatched.items())]
    write_csv(ART / "task_type_unmatched_values.csv", ["original_value", "count", "source_ids", "reason"], unmatched_csv)
    inventory = Counter()
    for row in after:
        value = row["task_type_components"] if row["task_type_standardization_status"] == "MULTI_TASK" else row["task_type"]
        inventory[(row["task_type_standardization_status"], value)] += 1
    write_csv(ART / "task_type_standardized_value_inventory.csv", ["classification", "standardized_value", "count"], [{"classification": kind, "standardized_value": value, "count": count} for (kind, value), count in sorted(inventory.items())])
    regression_tests = [{"csv_row": i, "status": "PASS" if row["task_type_standardization_status"] != "UNMATCHED" else "FAIL", "raw_value": row["task_type_original"], "standardization_status": row["task_type_standardization_status"]} for i, row in enumerate(after, start=2)]
    regression = {"business_rules_version": VERSION, "passed": sum(test["status"] == "PASS" for test in regression_tests), "failed": sum(test["status"] == "FAIL" for test in regression_tests), "tests": regression_tests}
    (ART / "task_type_standardization_regression_test.json").write_text(json.dumps(regression, ensure_ascii=False, indent=2), encoding="utf-8")
    audit = {"run_id": RUN.name, "audit_name": "task_type_standardization_v17_audit", "executed_at": datetime.now(timezone.utc).isoformat(), "rule_file": str(RULES.relative_to(ROOT)), "rule_version": VERSION, "frozen_status": rules["status"], "result": "PASS" if not errors else "FAIL", "checks": checks, "counts": {"total_records": len(after), "single_task": statuses["STANDARDIZED"], "multi_task": statuses["MULTI_TASK"], "excluded": statuses["EXCLUDED_BY_BUSINESS_RULE"], "unknown": statuses["UNKNOWN"], "unmatched": statuses["UNMATCHED"], "changed_records": sum(original.get("task_type", "") != row.get("task_type", "") for original, row in zip(before, after)), "non_task_type_changed_rows": len(changed_non_task)}, "checksums": {"backup": sha256(BACKUP), "standardized_dataset": sha256(DATASET)}}
    (ART / "task_type_standardization_v17_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    if errors:
        raise RuntimeError(f"Task Type Data Quality failed: {', '.join(errors)}")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
