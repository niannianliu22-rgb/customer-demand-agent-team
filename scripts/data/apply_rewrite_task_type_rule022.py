#!/usr/bin/env python3
"""Apply the human-confirmed RULE-022 rewrite-to-resit mapping to review artifacts.

This script intentionally does not read or write the unified dataset or any raw Excel.
"""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DIMENSION_REVIEW = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/dimension_review"
REWRITE_VALUES = {"2500词重写", "essay重写", "me重写"}
RESIT_VALUES = {
    "补考", "补考essay", "2h补考", "3h补考", "补考辅导", "2500词补考",
    "2500词重写", "3.5h补考", "3H补考", "essay补考", "essay重写", "me重写",
    "八小时补考", "六小时补考", "补考1500词", "补考2h", "补考6000词", "补考90mins",
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    final_path = DIMENSION_REVIEW / "task_type_manual_final_review_v2.csv"
    fields, rows = read_csv(final_path)
    found = set()
    for row in rows:
        if row["original_value"] in REWRITE_VALUES:
            found.add(row["original_value"])
            row["current_status"] = "REVIEW_REQUIRED"
            row["suggested_official_task_type"] = "补考"
            row["confidence"] = "HIGH"
            row["mapping_reason"] = (
                "RULE-022：当前公司业务口径中，重写属于补考业务；词数、essay、ME 等修饰"
                "信息不改变核心业务类型。"
            )
            row["risk_note"] = "manual_business_confirmation：重写不得映射为 essay 或 ME。"
            row["business_decision"] = "APPROVED"
            row["final_official_task_type"] = "补考"
            row["review_note"] = "manual_business_confirmation; RULE-022"
    if found != REWRITE_VALUES:
        raise RuntimeError(f"Missing rewrite values in final review: {sorted(REWRITE_VALUES - found)}")
    write_csv(final_path, fields, rows)

    business_path = DIMENSION_REVIEW / "task_type_business_final_review.csv"
    fields, rows = read_csv(business_path)
    found_resit = set()
    for row in rows:
        raw_value = row["raw_value"]
        if raw_value not in RESIT_VALUES:
            continue
        found_resit.add(raw_value)
        is_rewrite = raw_value in REWRITE_VALUES
        rule_id = "RULE-022" if is_rewrite else "RULE-021"
        reason = (
            "RULE-022：当前公司业务口径中，重写属于补考业务；不得按 essay 或 ME 底层任务类型分类。"
            if is_rewrite
            else "RULE-021：补考为独立 official task type；词数、时长、essay、辅导等修饰不改变核心业务类型。"
        )
        row["current_classification"] = "MANUAL_CONFIRMED_ALIAS"
        row["proposed_official_task_type"] = "补考"
        row["risk_flag"] = "NONE"
        row["model_recommendation"] = "补考"
        row["model_reason"] = reason
        row["evidence_status"] = "MANUAL_BUSINESS_CONFIRMATION"
        row["business_decision"] = "APPROVED"
        row["final_official_task_type"] = "补考"
        row["review_note"] = f"manual_business_confirmation; {rule_id}"
    if found_resit != RESIT_VALUES:
        raise RuntimeError(f"Missing resit values in business review: {sorted(RESIT_VALUES - found_resit)}")
    write_csv(business_path, fields, rows)

    alias_path = ROOT / "config/dimensions/task_type/rewrite_aliases.yaml"
    alias_path.write_text(
        "# ACTIVE rewrite aliases confirmed by business.\n"
        "aliases_version: \"1.0\"\n"
        "business_rules_version: \"12.0\"\n"
        "rule_id: RULE-022\n"
        "source: manual_business_confirmation\n"
        "status: ACTIVE\n"
        "restriction: >\n"
        "  Apply only the exact listed raw values. 重写 is a resit business type, not an\n"
        "  independent official task type and not an essay/ME subtype.\n"
        "entries:\n"
        + "".join(
            f'  - raw_value: "{value}"\n'
            '    canonical_task_type: "补考"\n'
            "    source: manual_business_confirmation\n"
            "    status: ACTIVE\n"
            for value in ("2500词重写", "essay重写", "me重写")
        ),
        encoding="utf-8",
    )
    print(f"Updated {len(found)} rewrite review rows and {len(found_resit)} resit/rewrite business-review rows.")


if __name__ == "__main__":
    main()
