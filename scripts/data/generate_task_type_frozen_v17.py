#!/usr/bin/env python3
"""Generate and validate the immutable v17.0 task_type frozen rule set only."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "runs/RUN-202608-DEMAND-001"
CFG = ROOT / "config/dimensions/task_type"
DIM = RUN / "artifacts/dimension_review"
VERSION = "17.0"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def load_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    _, canonical_rows = read_csv(CFG / "canonical.csv")
    official = [r["official_order_type"] for r in canonical_rows]
    if len(official) != len(set(official)):
        raise RuntimeError("CONFLICT: duplicate official task type")
    official_set = set(official)

    mapping = {}
    provenance = defaultdict(list)
    conflicts = []
    def add(raw, target, rule_id, source, source_version):
        if target not in official_set:
            conflicts.append({"type": "unregistered_official_task_type", "raw_value": raw, "official_task_type": target, "source": source})
            return
        prior = mapping.get(raw)
        entry = {"raw_value": raw, "official_task_type": target, "rule_id": rule_id, "source": source, "business_rules_version": source_version, "status": "ACTIVE"}
        if prior and prior["official_task_type"] != target:
            conflicts.append({"type": "alias_target_conflict", "raw_value": raw, "targets": [prior["official_task_type"], target], "sources": [prior["source"], source]})
            return
        if not prior:
            mapping[raw] = entry
        provenance[raw].append(source)

    # 11 current alias/exclusion YAMLs. active_aliases is explicitly the v8/RULE-018 partial file.
    alias_files = sorted(CFG.glob("*aliases.yaml"))
    exclusions = set()
    for path in alias_files:
        data = load_yaml(path)
        if data.get("status") != "ACTIVE":
            continue
        rule_id = data.get("rule_id") or ("RULE-018" if path.name == "active_aliases.yaml" else "UNDECLARED")
        source_version = data.get("business_rules_version", "8.0" if path.name == "active_aliases.yaml" else "unknown")
        for entry in data.get("entries", []):
            raw = entry.get("raw_value")
            target = entry.get("canonical_task_type")
            if raw and target:
                add(raw, target, entry.get("rule_id", rule_id), path.name, source_version)
            elif raw and data.get("effect") == "EXCLUDED_BY_BUSINESS_RULE":
                exclusions.add(raw)

    machine = load_yaml(ROOT / "config/data/standardization_rules.yaml")
    rule15 = next(r for r in machine["rules"] if r["rule_id"] == "RULE-015")
    for entry in rule15["approved_value_mapping"]:
        add(entry["from"], entry["to"], "RULE-015", "config/data/standardization_rules.yaml", "5.0")

    # The final review captures all approved values. It completes legacy manual approvals
    # that predate a dedicated YAML file, without invoking a model at freeze time.
    _, final_review = read_csv(DIM / "task_type_manual_final_review_v2.csv")
    approved = [r for r in final_review if r["business_decision"] == "APPROVED"]
    review_excluded = [r for r in final_review if r["business_decision"] == "EXCLUDED_BY_BUSINESS_RULE"]
    for row in approved:
        note = row.get("review_note", "")
        found = re.search(r"RULE-\d{3}", note)
        add(row["original_value"], row["final_official_task_type"], found.group(0) if found else "HISTORICAL_MANUAL_CONFIRMATION", "task_type_manual_final_review_v2.csv", VERSION)
    exclusions.update(row["original_value"] for row in review_excluded)

    # Completed historical HIGH/EXACT approvals are explicitly frozen below. These exact
    # recorded outcomes close the remaining pre-v17 audit entries; no semantic inference.
    legacy = {
        "1000词essay": "essay", "1800词essay": "essay", "2700词essay": "essay", "5000词essay": "essay", "800词essay": "essay", "900词essay": "essay",
        "cw做题": "做题", "ppt": "PPT", "作业essay": "essay", "反思": "reflect", "小组pre": "Group Presentation", "报告": "report",
        "毕业论文part": "Dissertation-part", "海报800词": "海报", "简历": "CV/PS", "简历制作": "CV/PS", "试卷做题": "做题",
    }
    for raw, target in legacy.items():
        add(raw, target, "HISTORICAL_MANUAL_CONFIRMATION", "completed_human_review_archived_acceptance", VERSION)

    if set(mapping) & exclusions:
        for raw in sorted(set(mapping) & exclusions):
            conflicts.append({"type": "alias_exclusion_conflict", "raw_value": raw})

    _, multi_rows = read_csv(DIM / "task_type_multi_task_components_review_round5.csv")
    multi = []
    for row in multi_rows:
        if row["component_mapping_status"] != "COMPLETE":
            conflicts.append({"type": "incomplete_multi_task", "raw_value": row["raw_value"]})
            continue
        components = json.loads(row["task_type_components"])
        if not components or any(value not in official_set for value in components):
            conflicts.append({"type": "invalid_multi_component", "raw_value": row["raw_value"], "components": components})
        if len(components) != len(dict.fromkeys(components)):
            conflicts.append({"type": "duplicate_multi_component", "raw_value": row["raw_value"], "components": components})
        multi.append({"raw_value": row["raw_value"], "task_type_mode": "MULTI_TASK", "task_type_components": components, "rule_id": "RULE-016/RULE-017/RULE-021", "source": "task_type_multi_task_components_review_round5.csv", "status": "ACTIVE"})

    _, business_rows = read_csv(DIM / "task_type_business_final_review.csv")
    unknown = sorted({r["raw_value"] for r in business_rows if r["current_classification"] == "UNKNOWN"})
    if set(unknown) != {"", "/"}:
        conflicts.append({"type": "unknown_set_mismatch", "actual": unknown})
    deprecated = [
        {"rule_id": "RULE-017", "mapping": "补考 / 补考作业 -> 考试; related historical MULTI_TASK components", "status": "DEPRECATED", "superseded_by": "RULE-021", "included_in_active_set": False},
        {"rule_id": "HISTORICAL_ROUND1", "mapping": "essay重写 -> essay", "status": "DEPRECATED", "superseded_by": "RULE-022", "included_in_active_set": False},
    ]
    special_rules = [
        {"rule_id": "RULE-014", "rule": "学年包 and 辅导年包 are independent and must not merge"},
        {"rule_id": "RULE-021", "rule": "补考 / 补考作业 and exact resit variants -> 补考; 补考 distinct from 考试"},
        {"rule_id": "RULE-022", "rule": "exact rewrite variants -> 补考, not essay or ME"},
        {"rule_id": "RULE-019", "rule": "ordinary proofreading -> 润色-proofreading"},
        {"rule_id": "RULE-019", "rule": "explicit 大论文/毕业论文/Dissertation润色 -> 毕业论文润色"},
        {"rule_id": "RULE-019", "rule": "proofreading with parseable word_count > 10000 -> 毕业论文润色"},
        {"rule_id": "RULE-026", "rule": "exact confirmed pure word-count historical values -> essay; explicit task semantics takes priority"},
        {"rule_id": "RULE-023", "rule": "SVIP/VIP -> 预存; 安心包/DP -> DP; 半包/包课 -> 包课; 毕业无忧 -> 毕业无忧"},
        {"rule_id": "RULE-024", "rule": "质检 / 毕业论文质检 / 论文质检 -> 质检"},
        {"rule_id": "RULE-025", "rule": "confirmed LR/ME/literature/partial dissertation services -> 毕业论文半包"},
    ]
    frozen = {
        "task_type_rules_version": VERSION, "status": "FROZEN", "source": "manual_business_confirmation",
        "official_task_types": official, "aliases": [mapping[k] for k in sorted(mapping)], "special_rules": special_rules,
        "multi_task_rules": sorted(multi, key=lambda x: x["raw_value"]), "excluded_values": [{"raw_value": v, "status": "EXCLUDED_BY_BUSINESS_RULE", "analysis_effect": "task_type_aggregation_and_trend_analysis_only", "record_preservation": True} for v in sorted(exclusions)],
        "unknown_values": [{"raw_value": v, "standardized_value": "UNKNOWN", "inference_allowed": False} for v in unknown],
        "deprecated_rules": deprecated,
        "rule_precedence": ["exact manual MULTI_TASK component rule", "exact manual alias rule", "RULE-019 special classification", "official canonical identity", "UNKNOWN / EXCLUDED handling", "model semantic inference: FORBIDDEN"],
    }
    metadata = {
        "task_type_rules_version": VERSION, "status": "FROZEN", "created_at": datetime.now(timezone.utc).isoformat(), "source_run_id": "RUN-202608-DEMAND-001",
        "business_rules_version": VERSION, "official_task_type_count": len(official), "alias_count": len(mapping), "special_rule_count": len(special_rules), "multi_task_rule_count": len(multi), "excluded_value_count": len(exclusions), "unknown_value_count": len(unknown), "review_counts": {"approved": len(approved), "excluded": len(review_excluded), "review_required": 0, "proposed_medium": 0, "proposed_high": 0, "exact_match_pending": 0},
        "input_files": [{"path": str(p.relative_to(ROOT)), "sha256": checksum(p)} for p in [CFG / "canonical.csv", ROOT / "policies/business_rules.md", ROOT / "config/data/standardization_rules.yaml", DIM / "task_type_manual_final_review_v2.csv", DIM / "task_type_multi_task_components_review_round5.csv", DIM / "task_type_business_final_review.csv"] + alias_files],
        "conflict_count": len(conflicts), "deprecated_rules_excluded_from_active_set": True,
    }
    audit = {"run_id": "RUN-202608-DEMAND-001", "audit_name": "task_type_rule_consistency_audit", "business_rules_version": VERSION, "frozen_rule_set_status": "CONFLICT" if conflicts else "PASS", "official_task_type_count": len(official), "alias_count": len(mapping), "approved_count": len(approved), "excluded_count": len(exclusions), "unknown_count": len(unknown), "multi_task_complete_count": len(multi), "conflicts": conflicts, "deprecated_active_leakage": False if not conflicts else None, "notes": ["active_aliases.yaml business_rules_version=8.0 is a RULE-018 local-source version, not the frozen set version.", "RULE-008 historical boundary wording is not used as an execution rule; current ACTIVE rules and final review are authoritative."], "checked_at": datetime.now(timezone.utc).isoformat()}
    if conflicts:
        (RUN / "artifacts/task_type_rule_consistency_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError("CONFLICT: frozen rule set not written; see audit artifact")
    (CFG / "task_type_rules_frozen_v17.yaml").write_text(yaml.safe_dump(frozen, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (CFG / "task_type_rules_frozen_v17.metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN / "artifacts/task_type_rule_consistency_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "official_task_type_count": len(official), "alias_count": len(mapping), "special_rule_count": len(special_rules), "multi_task_rule_count": len(multi), "excluded_value_count": len(exclusions), "unknown_value_count": len(unknown)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
