#!/usr/bin/env python3
"""Apply manually confirmed Round-6 MULTI_TASK component mappings only."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TASK_DIR = ROOT / "config" / "dimensions" / "task_type"
CANONICAL = TASK_DIR / "canonical.csv"
REVIEW_DIR = ROOT / "runs" / "RUN-202608-DEMAND-001" / "artifacts" / "dimension_review"
BUSINESS = REVIEW_DIR / "task_type_business_final_review.csv"
AUDIT = REVIEW_DIR / "task_type_multi_task_components_review_round5.csv"

ADDITIONS = [
    ("数据收集", "MANUAL-TASK-TYPE-004"),
    ("降重", "MANUAL-TASK-TYPE-005"),
    ("入学测试", "MANUAL-TASK-TYPE-006"),
]
UPDATES = {
    "数据收集+分析": ["数据收集", "Analysis"],
    "润色+降重+续写2000词": ["润色-proofreading", "降重", "essay"],
    "补考➕毕业论文": ["考试", "Dissertation"],
    "补考作业+考试": ["考试"],
    "选课+入学测试": ["选课", "入学测试"],
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def stage(path: Path, fields: list[str], rows: list[dict[str, str]]) -> Path:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8-sig", newline="", dir=path.parent, delete=False
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
        return Path(handle.name)


def by_raw(rows: list[dict[str, str]], raw_value: str) -> dict[str, str]:
    matches = [row for row in rows if row["raw_value"] == raw_value]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one row for {raw_value!r}; got {len(matches)}")
    return matches[0]


def main() -> None:
    canonical_fields, canonical_rows = read_csv(CANONICAL)
    existing = {row["official_order_type"]: row for row in canonical_rows}
    for name, identifier in ADDITIONS:
        if name in existing:
            if existing[name]["official_task_type_id"] != identifier:
                raise ValueError(f"Unexpected existing canonical row for {name}")
            continue
        canonical_rows.append(
            {
                "official_task_type_id": identifier,
                "official_task_type_id_source": "manual_business_confirmation",
                "official_order_type": name,
                "official_source_record_id": "RULE-017",
                "official_numeric_value": "",
            }
        )
    official = {row["official_order_type"] for row in canonical_rows}
    for components in UPDATES.values():
        if not set(components) <= official:
            raise ValueError("A component is not an official task type")

    business_fields, business_rows = read_csv(BUSINESS)
    audit_fields, audit_rows = read_csv(AUDIT)
    for raw_value, components in UPDATES.items():
        business = by_raw(business_rows, raw_value)
        audit = by_raw(audit_rows, raw_value)
        for row in (business, audit):
            row.update(
                {
                    "task_type_components": json.dumps(components, ensure_ascii=False),
                    "unresolved_components": "[]",
                    "component_mapping_status": "COMPLETE",
                }
            )
        business.update(
            {
                "model_recommendation": "MULTI_TASK_COMPONENTS_STANDARDIZED",
                "model_reason": "RULE-017：保留 MULTI_TASK 模式；按人工确认的正式组件映射并去重，不压缩为单一 task_type。",
                "evidence_status": "MANUAL_BUSINESS_CONFIRMATION",
                "business_decision": "APPROVED_COMPONENT_SPLIT",
                "final_official_task_type": "",
                "review_note": "manual_business_confirmation",
                "recommended_task_type_list": "|".join(components),
            }
        )
        audit.update(
            {
                "evidence": "RULE-017 manual_business_confirmation：" + " | ".join(components),
                "decision": "APPROVED_COMPONENT_SPLIT",
                "review_note": "manual_business_confirmation",
            }
        )

    staged_canonical = stage(CANONICAL, canonical_fields, canonical_rows)
    staged_business = stage(BUSINESS, business_fields, business_rows)
    staged_audit = stage(AUDIT, audit_fields, audit_rows)
    os.replace(staged_canonical, CANONICAL)
    os.replace(staged_business, BUSINESS)
    os.replace(staged_audit, AUDIT)
    print(f"official_task_type_count={len(canonical_rows)}")
    print("multi_task_rows_updated=5")


if __name__ == "__main__":
    main()
