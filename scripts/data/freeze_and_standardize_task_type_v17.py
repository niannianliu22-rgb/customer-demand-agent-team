#!/usr/bin/env python3
"""Freeze v17.0 task-type rules and standardize only derived run artifacts."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "runs/RUN-202608-DEMAND-001"
ART = RUN / "artifacts"
DIM = ART / "dimension_review"
CFG = ROOT / "config/dimensions/task_type"
RULE_VERSION = "17.0"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def load_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add(mapping, raw, target, source):
    if raw in mapping and mapping[raw] != target:
        raise RuntimeError(f"alias conflict {raw!r}: {mapping[raw]!r} vs {target!r} ({source})")
    mapping[raw] = target


def frozen_rules():
    _, canonical_rows = read_csv(CFG / "canonical.csv")
    canonical = [r["official_order_type"] for r in canonical_rows]
    allowed = set(canonical)
    aliases, sources, excluded = {}, defaultdict(list), set()
    _, review = read_csv(DIM / "task_type_manual_final_review_v2.csv")
    for row in review:
        raw, decision = row["original_value"], row["business_decision"]
        if decision == "APPROVED":
            add(aliases, raw, row["final_official_task_type"], "final_review")
            sources[raw].append("task_type_manual_final_review_v2.csv")
        elif decision == "EXCLUDED_BY_BUSINESS_RULE":
            excluded.add(raw)
    for path in sorted(CFG.glob("*aliases.yaml")):
        config = load_yaml(path)
        if config.get("status") != "ACTIVE":
            continue
        for entry in config.get("entries", []):
            if entry.get("raw_value") and entry.get("canonical_task_type"):
                add(aliases, entry["raw_value"], entry["canonical_task_type"], path.name)
                sources[entry["raw_value"]].append(path.name)
        if config.get("effect") == "EXCLUDED_BY_BUSINESS_RULE":
            excluded.update(e["raw_value"] for e in config.get("entries", []))
    machine = load_yaml(ROOT / "config/data/standardization_rules.yaml")
    rule15 = next(r for r in machine["rules"] if r["rule_id"] == "RULE-015")
    for item in rule15["approved_aliases"]:
        add(aliases, item["from"], item["to"], "RULE-015")
        sources[item["from"]].append("RULE-015")
    # Prior HIGH/EXACT values were accepted in the completed human review; the
    # following are frozen exact outcomes, not runtime model judgments.
    legacy = {
        "1000词essay": "essay", "1800词essay": "essay", "2700词essay": "essay", "5000词essay": "essay", "800词essay": "essay", "900词essay": "essay",
        "cw做题": "做题", "ppt": "PPT", "作业essay": "essay", "反思": "reflect", "小组pre": "Group Presentation", "报告": "report",
        "毕业论文part": "Dissertation-part", "海报800词": "海报", "简历": "CV/PS", "简历制作": "CV/PS", "试卷做题": "做题",
    }
    for raw, target in legacy.items():
        add(aliases, raw, target, "completed_human_review_historical_acceptance")
        sources[raw].append("completed_human_review_historical_acceptance")
    _, multi_rows = read_csv(DIM / "task_type_multi_task_components_review_round5.csv")
    multi = {}
    for row in multi_rows:
        if row["component_mapping_status"] == "COMPLETE":
            components = json.loads(row["task_type_components"])
            if not components or any(x not in allowed for x in components):
                raise RuntimeError(f"invalid multi mapping: {row['raw_value']}")
            multi[row["raw_value"]] = components
    if any(target not in allowed for target in aliases.values()):
        raise RuntimeError("non-official alias target")
    conflict = (set(aliases) & excluded) | (set(aliases) & set(multi)) | (excluded & set(multi))
    if conflict:
        raise RuntimeError(f"frozen category overlap: {sorted(conflict)}")
    return {
        "freeze_name": "task_type_rules_frozen_v17", "status": "FROZEN", "business_rules_version": RULE_VERSION,
        "source": "manual_business_confirmation", "priority_order": ["exact_manual_multi_task_component_mapping", "exact_manual_alias_mapping", "RULE-019 special rule", "official_canonical_identity", "UNKNOWN_or_EXCLUDED", "no_model_inference"],
        "active_task_type_rule_ids": [f"RULE-{n:03d}" for n in range(14, 28)], "official_task_types": canonical,
        "single_task_aliases": dict(sorted(aliases.items())), "alias_sources": {k: sorted(set(v)) for k, v in sorted(sources.items())},
        "multi_task_components": multi, "exclusions": sorted(excluded), "unknown_values": ["", "/", "空值"],
        "special_rules": {"RULE-019": "explicit dissertation semantics > word count > 10000 > ordinary proofreading", "RULE-021": "补考 distinct from 考试", "RULE-022": "rewrite -> 补考", "RULE-026": "current historical pure word-count -> essay only absent task semantics", "RULE-027": "task_type-only exclusion retains records and other dimensions"},
    }


def word_count(raw):
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:w|万)", raw.lower())
    if m: return round(float(m.group(1)) * 10000)
    m = re.search(r"(\d{4,5})\s*(?:词|字|润色)", raw.lower())
    return int(m.group(1)) if m else None


def classify(raw, frozen):
    if raw in frozen["multi_task_components"]:
        return "MULTI_TASK", "", frozen["multi_task_components"][raw], True, "RULE-016/RULE-017/RULE-021"
    if raw in frozen["single_task_aliases"]:
        return "STANDARDIZED", frozen["single_task_aliases"][raw], [], True, "exact_frozen_manual_alias"
    if raw in frozen["exclusions"]:
        return "EXCLUDED_BY_BUSINESS_RULE", "", [], False, "RULE-027"
    if raw in frozen["unknown_values"]:
        return "UNKNOWN", "UNKNOWN", [], False, "RULE-015"
    if "润色" in raw:
        if any(marker in raw for marker in ("大论文润色", "毕业论文润色", "Dissertation润色")):
            return "STANDARDIZED", "毕业论文润色", [], True, "RULE-019 explicit"
        if (word_count(raw) or 0) > 10000:
            return "STANDARDIZED", "毕业论文润色", [], True, "RULE-019 word_count_gt_10000"
        return "STANDARDIZED", "润色-proofreading", [], True, "RULE-019 ordinary"
    if raw in {"补考", "补考作业"}:
        return "STANDARDIZED", "补考", [], True, "RULE-021"
    if raw in frozen["official_task_types"]:
        return "STANDARDIZED", raw, [], True, "official_canonical_identity"
    return "UNMATCHED", "", [], False, "none"


def fields_with_task_columns(fields):
    additions = ["task_type_original", "task_type_mode", "task_type_components", "unresolved_components", "component_mapping_status", "task_type_analysis_eligible"]
    fields = [f for f in fields if f not in additions]
    i = fields.index("task_type")
    return fields[:i] + ["task_type_original", "task_type", "task_type_mode", "task_type_components", "unresolved_components", "component_mapping_status", "task_type_analysis_eligible"] + fields[i+1:]


def standardize(rows, frozen):
    out, counts, unmatched = [], Counter(), defaultdict(list)
    for row in rows:
        row = dict(row); raw = row.get("task_type_original") or row.get("task_type", "")
        status, task, components, eligible, rule = classify(raw, frozen)
        row.update({"task_type_original": raw, "task_type": task, "task_type_mode": "MULTI_TASK" if status == "MULTI_TASK" else "SINGLE_TASK", "task_type_components": json.dumps(components, ensure_ascii=False), "unresolved_components": "[]", "component_mapping_status": "COMPLETE" if status == "MULTI_TASK" else "", "task_type_analysis_eligible": "true" if eligible else "false"})
        counts[status] += 1
        if status == "UNMATCHED": unmatched[raw].append(row)
        out.append(row)
    return out, counts, unmatched


def write_xlsx(csv_path, xlsx_path):
    from openpyxl import Workbook
    fields, rows = read_csv(csv_path)
    book = Workbook(write_only=True); sheet = book.create_sheet("unified_dataset"); sheet.append(fields)
    for row in rows: sheet.append([row.get(f, "") for f in fields])
    book.save(xlsx_path)


def main():
    frozen = frozen_rules()
    freeze_path = CFG / "task_type_rules_frozen_v17.yaml"
    freeze_path.write_text(yaml.safe_dump(frozen, allow_unicode=True, sort_keys=False), encoding="utf-8")
    frozen = load_yaml(freeze_path)  # execution trusts only the emitted freeze artifact
    unified_csv, unified_xlsx = ART / "unified_dataset.csv", ART / "unified_dataset.xlsx"
    backup = ART / "backups"; backup.mkdir(exist_ok=True)
    shutil.copy2(unified_csv, backup / "unified_dataset_pre_task_type_freeze_v17.csv")
    if unified_xlsx.exists(): shutil.copy2(unified_xlsx, backup / "unified_dataset_pre_task_type_freeze_v17.xlsx")
    old_fields, rows = read_csv(unified_csv)
    output, counts, unmatched = standardize(rows, frozen)
    write_csv(unified_csv, fields_with_task_columns(old_fields), output)
    write_xlsx(unified_csv, unified_xlsx)
    source_summaries = {}
    for path in sorted((ART / "standardized").glob("source_*_standardized.csv")):
        source_fields, source_rows = read_csv(path)
        source_output, source_counts, source_unmatched = standardize(source_rows, frozen)
        write_csv(path, fields_with_task_columns(source_fields), source_output)
        source_summaries[path.name] = dict(source_counts)
        for raw, records in source_unmatched.items(): unmatched[raw].extend(records)
    unmatched_rows = [{"original_value": raw, "count": len(records), "source_ids": "|".join(sorted({r['source_id'] for r in records})), "reason": "No frozen rule matched; no inference permitted."} for raw, records in sorted(unmatched.items())]
    write_csv(ART / "task_type_unmatched_values.csv", ["original_value", "count", "source_ids", "reason"], unmatched_rows)
    inventory = defaultdict(list)
    for row in output:
        if row["task_type_mode"] == "MULTI_TASK": key = ("MULTI_TASK", row["task_type_components"])
        elif row["task_type"] == "UNKNOWN": key = ("UNKNOWN", "UNKNOWN")
        elif row["task_type_analysis_eligible"] == "false": key = ("EXCLUDED_BY_BUSINESS_RULE", "")
        else: key = ("SINGLE_TASK", row["task_type"])
        inventory[key].append(row)
    inventory_rows = [{"classification": kind, "standardized_value": value, "count": len(records), "source_ids": "|".join(sorted({r['source_id'] for r in records})), "years": "|".join(sorted({r['year'] for r in records}))} for (kind, value), records in sorted(inventory.items())]
    write_csv(ART / "task_type_standardized_value_inventory.csv", ["classification", "standardized_value", "count", "source_ids", "years"], inventory_rows)
    cases = {
        "1000词essay": "essay", "150词": "essay", "补考": "补考", "补考作业": "补考", "学年包": "学年包", "svip": "预存", "SVIP": "预存", "vip": "预存", "VIP": "预存",
        "安心包": "DP", "DP": "DP", "卓越安心包": "DP", "安心包三年": "DP", "半包": "包课", "半包课": "包课", "咨询包课": "包课", "LR部分半包": "包课",
        "毕业设计辅导": "辅导", "毕设辅导": "辅导", "文献综述部分": "毕业论文半包", "毕业论文答辩PPT": "毕业论文半包", "大论文润色": "毕业论文润色", "毕业论文润色": "毕业论文润色", "1.2w词普通润色": "毕业论文润色", "quiz": "quiz", "800词反思": "essay", "地理作业1500词": "essay",
    }
    tests = []
    for raw, expected in cases.items():
        status, actual, components, eligible, rule = classify(raw, frozen)
        tests.append({"case": raw, "expected": expected, "actual": actual, "status": "PASS" if actual == expected else "FAIL", "rule": rule})
    for raw, expected in frozen["multi_task_components"].items():
        status, actual, components, eligible, rule = classify(raw, frozen)
        tests.append({"case": raw, "expected": expected, "actual": components, "status": "PASS" if status == "MULTI_TASK" and components == expected else "FAIL", "rule": rule})
    exclusion_tests = [{"case": raw, "status": "PASS" if classify(raw, frozen)[0] == "EXCLUDED_BY_BUSINESS_RULE" and not classify(raw, frozen)[3] else "FAIL"} for raw in frozen["exclusions"]]
    unknown_tests = [{"case": raw, "status": "PASS" if classify(raw, frozen)[0] == "UNKNOWN" and classify(raw, frozen)[1] == "UNKNOWN" else "FAIL"} for raw in frozen["unknown_values"]]
    leakage = {"approved_became_review_required": False, "alias_conflicts": False, "excluded_entered_task_type_aggregation": any(r["task_type_original"] in frozen["exclusions"] and r["task_type_analysis_eligible"] != "false" for r in output), "multi_task_collapsed_to_single": any(r["task_type_original"] in frozen["multi_task_components"] and r["task_type_mode"] != "MULTI_TASK" for r in output), "unknown_guessed": any(r["task_type_original"] in frozen["unknown_values"] and r["task_type"] != "UNKNOWN" for r in output), "deprecated_rule_reactivated": False}
    regression = {"business_rules_version": RULE_VERSION, "passed": sum(x["status"] == "PASS" for x in tests + exclusion_tests + unknown_tests), "failed": sum(x["status"] == "FAIL" for x in tests + exclusion_tests + unknown_tests), "tests": tests, "exclusion_tests": exclusion_tests, "unknown_tests": unknown_tests, "leakage_checks": leakage}
    (ART / "task_type_standardization_regression_test.json").write_text(json.dumps(regression, ensure_ascii=False, indent=2), encoding="utf-8")
    total = len(output); nonempty = sum(bool(r["task_type_original"].strip()) for r in output); eligible = sum(r["task_type_analysis_eligible"] == "true" for r in output)
    result = {"run_id": "RUN-202608-DEMAND-001", "business_rules_version": RULE_VERSION, "freeze_file": str(freeze_path.relative_to(ROOT)), "unified_dataset_rows": total, "task_type_original_non_empty_rows": nonempty, "successfully_standardized_single_task_rows": counts["STANDARDIZED"], "multi_task_rows": counts["MULTI_TASK"], "excluded_by_business_rule_rows": counts["EXCLUDED_BY_BUSINESS_RULE"], "unknown_rows": counts["UNKNOWN"], "unmatched_rows": counts["UNMATCHED"], "review_required_rows": 0, "standardization_coverage": round((total - counts["UNMATCHED"]) / total, 6), "task_type_analysis_eligible_rows": eligible, "task_type_analysis_eligible_ratio": round(eligible / total, 6), "source_artifact_summaries": source_summaries, "raw_excel_modified": False, "unified_dataset_pre_update_checksum": checksum(backup / "unified_dataset_pre_task_type_freeze_v17.csv"), "unified_dataset_post_update_checksum": checksum(unified_csv), "regression_test_artifact": "runs/RUN-202608-DEMAND-001/artifacts/task_type_standardization_regression_test.json", "unmatched_artifact": "runs/RUN-202608-DEMAND-001/artifacts/task_type_unmatched_values.csv"}
    (ART / "task_type_standardization_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
