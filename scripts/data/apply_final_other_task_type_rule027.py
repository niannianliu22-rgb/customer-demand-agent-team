#!/usr/bin/env python3
"""Apply human-confirmed RULE-027 to F-group review/config artifacts only."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/dimension_review"
APPROVED = {
    "quiz": "quiz",
    "毕业设计辅导": "辅导",
    "毕设辅导": "辅导",
    "800词反思": "essay",
    "地理作业1500词": "essay",
}
EXCLUDED = {
    "2h高级财务", "3000词方法论", "3题", "unity", "两个小作业", "写一个升学的kit",
    "帮忙收集数据", "总结", "毕业影集", "深润2000词", "画图", "续写", "网站制作",
    "计算机科学", "选课课程内容分析", "采访稿", "重修", "面试", "题目",
}
ALL_VALUES = set(APPROVED) | EXCLUDED


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
        if raw not in ALL_VALUES:
            continue
        found.add(raw)
        if raw in APPROVED:
            target = APPROVED[raw]
            row["suggested_official_task_type"] = target
            if "confidence" in row:
                row["confidence"] = "HIGH"
            if "reason" in row:
                row["reason"] = "RULE-027：按人工确认的精确任务类型映射。"
            if "ambiguity_reason" in row:
                row["ambiguity_reason"] = "已由人工业务确认消除歧义。"
            if "mapping_reason" in row:
                row["mapping_reason"] = "RULE-027：按人工确认的精确任务类型映射。"
            if "risk_note" in row:
                row["risk_note"] = "manual_business_confirmation：仅适用于 RULE-027 列明值。"
            if "current_status" in row:
                row["current_status"] = "MANUAL_CONFIRMED_ALIAS"
            row["business_decision"] = "APPROVED"
            row["final_official_task_type"] = target
            row["review_note"] = "manual_business_confirmation; RULE-027"
        else:
            row["suggested_official_task_type"] = ""
            if "confidence" in row:
                row["confidence"] = "N/A"
            if "reason" in row:
                row["reason"] = "RULE-027：从本项目 task_type 聚合及趋势分析口径排除。"
            if "ambiguity_reason" in row:
                row["ambiguity_reason"] = "人工确认当前无法唯一映射；仅排除 task_type 分析，不删除记录。"
            if "mapping_reason" in row:
                row["mapping_reason"] = "RULE-027：仅排除 task_type 分析；保留 task_type_original 与整行来源追溯。"
            if "risk_note" in row:
                row["risk_note"] = "EXCLUDED_BY_BUSINESS_RULE：学校、日期、金额、渠道等其他维度仍可使用。"
            if "current_status" in row:
                row["current_status"] = "EXCLUDED_BY_BUSINESS_RULE"
            row["business_decision"] = "EXCLUDED_BY_BUSINESS_RULE"
            row["final_official_task_type"] = ""
            row["review_note"] = "manual_business_confirmation; RULE-027; task_type_only"
    if found != ALL_VALUES:
        raise RuntimeError(f"Missing F-group values in {path.name}: {sorted(ALL_VALUES-found)}")
    write_csv(path, fields, rows)
    return len(found)


def update_business_review(path: Path) -> int:
    fields, rows = read_csv(path)
    found = set()
    for row in rows:
        raw = row["raw_value"]
        if raw not in ALL_VALUES:
            continue
        found.add(raw)
        if raw in APPROVED:
            target = APPROVED[raw]
            row["current_classification"] = "MANUAL_CONFIRMED_ALIAS"
            row["proposed_official_task_type"] = target
            row["risk_flag"] = "NONE"
            row["model_recommendation"] = target
            row["model_reason"] = "RULE-027：按人工确认的精确任务类型映射。"
            row["evidence_status"] = "MANUAL_BUSINESS_CONFIRMATION"
            row["business_decision"] = "APPROVED"
            row["final_official_task_type"] = target
            row["review_note"] = "manual_business_confirmation; RULE-027"
        else:
            row["current_classification"] = "EXCLUDED_BY_BUSINESS_RULE"
            row["proposed_official_task_type"] = ""
            row["risk_flag"] = "TASK_TYPE_ONLY_EXCLUSION"
            row["model_recommendation"] = ""
            row["model_reason"] = "RULE-027：仅排除 task_type 聚合与趋势分析；原始记录及其他维度保留。"
            row["evidence_status"] = "MANUAL_BUSINESS_CONFIRMATION"
            row["business_decision"] = "EXCLUDED_BY_BUSINESS_RULE"
            row["final_official_task_type"] = ""
            row["review_note"] = "manual_business_confirmation; RULE-027; task_type_only"
    if found != ALL_VALUES:
        raise RuntimeError(f"Missing F-group values in {path.name}: {sorted(ALL_VALUES-found)}")
    write_csv(path, fields, rows)
    return len(found)


def add_to_canonical() -> None:
    path = ROOT / "config/dimensions/task_type/canonical.csv"
    fields, rows = read_csv(path)
    for task_id, task_type in (("MANUAL-TASK-TYPE-015", "quiz"), ("MANUAL-TASK-TYPE-016", "辅导")):
        if not any(row["official_order_type"] == task_type for row in rows):
            rows.append({"official_task_type_id": task_id, "official_task_type_id_source": "manual_business_confirmation", "official_order_type": task_type, "official_source_record_id": "RULE-027", "official_numeric_value": ""})
    write_csv(path, fields, rows)


def write_config() -> None:
    approved_path = ROOT / "config/dimensions/task_type/final_other_confirmed_aliases.yaml"
    lines = ["# ACTIVE exact F-group aliases confirmed by business.", 'aliases_version: "1.0"', 'business_rules_version: "17.0"', "rule_id: RULE-027", "source: manual_business_confirmation", "status: ACTIVE", "restriction: Apply only exact listed raw values.", "entries:"]
    for raw, target in APPROVED.items():
        lines.extend([f'  - raw_value: "{raw}"', f'    canonical_task_type: "{target}"', "    source: manual_business_confirmation", "    status: ACTIVE"])
    approved_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    excluded_path = ROOT / "config/dimensions/task_type/final_other_task_type_exclusions.yaml"
    lines = ["# ACTIVE task_type-only exclusions confirmed by business.", 'exclusions_version: "1.0"', 'business_rules_version: "17.0"', "rule_id: RULE-027", "source: manual_business_confirmation", "status: ACTIVE", "effect: EXCLUDED_BY_BUSINESS_RULE", "restriction: Preserve task_type_original, source traceability, record, and all non-task-type dimensions.", "entries:"]
    for raw in sorted(EXCLUDED):
        lines.extend([f'  - raw_value: "{raw}"', "    exclusion_scope: task_type_aggregation_and_trend_analysis_only", "    source: manual_business_confirmation", "    status: ACTIVE"])
    excluded_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    n1 = update_review(REVIEW_DIR / "task_type_manual_final_review_v2.csv", "original_value")
    n2 = update_review(REVIEW_DIR / "task_type_review_required_reorganized.csv", "original_value")
    n3 = update_business_review(REVIEW_DIR / "task_type_business_final_review.csv")
    add_to_canonical()
    write_config()
    print(f"Updated {n1} manual-final, {n2} reorganized, and {n3} business-review F-group values.")


if __name__ == "__main__":
    main()
