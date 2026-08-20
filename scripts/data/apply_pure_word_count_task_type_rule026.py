#!/usr/bin/env python3
"""Apply human-confirmed RULE-026 to E-group review/config artifacts only."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/dimension_review"
MAPPINGS = {value: "essay" for value in (
    "150词", "1200词", "2000词", "3000词", "1000词", "1100词", "1200-1500词", "1500词", "1700词",
    "200词", "300词", "3k词", "4000词", "4500", "600词", "750词", "900词", "三千词",
)}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def update_review(path: Path, value_key: str) -> int:
    fields, rows = read_csv(path)
    found = set()
    for row in rows:
        raw = row[value_key]
        if raw not in MAPPINGS:
            continue
        found.add(raw)
        row["suggested_official_task_type"] = "essay"
        if "confidence" in row:
            row["confidence"] = "HIGH"
        if "reason" in row:
            row["reason"] = "RULE-026：当前历史数据中仅含字数／词数、无明确任务语义的值统一映射 essay。"
        if "ambiguity_reason" in row:
            row["ambiguity_reason"] = "已由人工业务确认消除歧义；未来带明确任务语义的值不适用本规则。"
        if "mapping_reason" in row:
            row["mapping_reason"] = "RULE-026：纯字数历史值映射 essay；明确任务语义优先。"
        if "risk_note" in row:
            row["risk_note"] = "manual_business_confirmation：仅限当前历史口径及无明确任务语义的纯字数值。"
        if "current_status" in row:
            row["current_status"] = "MANUAL_CONFIRMED_ALIAS"
        row["business_decision"] = "APPROVED"
        row["final_official_task_type"] = "essay"
        row["review_note"] = "manual_business_confirmation; RULE-026"
    if found != set(MAPPINGS):
        raise RuntimeError(f"Missing E-group values in {path.name}: {sorted(set(MAPPINGS)-found)}")
    write_csv(path, fields, rows)
    return len(found)


def update_business_review(path: Path) -> int:
    fields, rows = read_csv(path)
    found = set()
    for row in rows:
        raw = row["raw_value"]
        if raw not in MAPPINGS:
            continue
        found.add(raw)
        row["current_classification"] = "MANUAL_CONFIRMED_ALIAS"
        row["proposed_official_task_type"] = "essay"
        row["risk_flag"] = "NONE"
        row["model_recommendation"] = "essay"
        row["model_reason"] = "RULE-026：当前历史数据中无明确任务语义的纯字数值映射 essay。"
        row["evidence_status"] = "MANUAL_BUSINESS_CONFIRMATION"
        row["business_decision"] = "APPROVED"
        row["final_official_task_type"] = "essay"
        row["review_note"] = "manual_business_confirmation; RULE-026"
    if found != set(MAPPINGS):
        raise RuntimeError(f"Missing E-group values in {path.name}: {sorted(set(MAPPINGS)-found)}")
    write_csv(path, fields, rows)
    return len(found)


def write_aliases() -> None:
    path = ROOT / "config/dimensions/task_type/pure_word_count_essay_aliases.yaml"
    lines = ["# ACTIVE historical pure-word-count aliases confirmed by business.", 'aliases_version: "1.0"', 'business_rules_version: "16.0"', "rule_id: RULE-026", "source: manual_business_confirmation", "status: ACTIVE", "scope: RUN-202608-DEMAND-001 historical task_type values only", "priority: explicit_task_semantics > special_business_rule > pure_word_count_to_essay", "restriction: Do not apply to values with explicit task semantics (for example report, reflection, methodology).", "entries:"]
    for raw in MAPPINGS:
        lines.extend([f'  - raw_value: "{raw}"', '    canonical_task_type: "essay"', "    source: manual_business_confirmation", "    status: ACTIVE"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    n1 = update_review(REVIEW_DIR / "task_type_manual_final_review_v2.csv", "original_value")
    n2 = update_review(REVIEW_DIR / "task_type_review_required_reorganized.csv", "original_value")
    n3 = update_business_review(REVIEW_DIR / "task_type_business_final_review.csv")
    write_aliases()
    print(f"Updated {n1} manual-final, {n2} reorganized, and {n3} business-review E-group values.")


if __name__ == "__main__":
    main()
