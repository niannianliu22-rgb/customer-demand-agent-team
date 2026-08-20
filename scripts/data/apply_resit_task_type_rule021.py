#!/usr/bin/env python3
"""Apply the manually confirmed standalone resit task type (RULE-021)."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TASK_DIR = ROOT / "config" / "dimensions" / "task_type"
CANONICAL = TASK_DIR / "canonical.csv"
ALIASES = TASK_DIR / "resit_aliases.yaml"
DIMENSION = ROOT / "runs" / "RUN-202608-DEMAND-001" / "artifacts" / "dimension_review"
FINAL_REVIEW = DIMENSION / "task_type_manual_final_review_v2.csv"
BUSINESS_REVIEW = DIMENSION / "task_type_business_final_review.csv"
MULTI_AUDIT = DIMENSION / "task_type_multi_task_components_review_round5.csv"
RESIT = "补考"
RESIT_ID = "MANUAL-TASK-TYPE-011"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def stage_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> Path:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="", dir=path.parent, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
        return Path(handle.name)


def stage_text(path: Path, text: str) -> Path:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        return Path(handle.name)


def q(value: str) -> str:
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def is_resit(raw: str) -> bool:
    return "补考" in raw or "重写" in raw


def row_by_raw(rows: list[dict[str, str]], raw: str) -> dict[str, str]:
    matches = [row for row in rows if row["raw_value"] == raw]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one row for {raw!r}")
    return matches[0]


def main() -> None:
    canonical_fields, canonical_rows = read_csv(CANONICAL)
    existing = {row["official_order_type"]: row for row in canonical_rows}
    if RESIT not in existing:
        canonical_rows.append({
            "official_task_type_id": RESIT_ID,
            "official_task_type_id_source": "manual_business_confirmation",
            "official_order_type": RESIT,
            "official_source_record_id": "RULE-021",
            "official_numeric_value": "",
        })
    elif existing[RESIT]["official_task_type_id"] != RESIT_ID:
        raise ValueError("Unexpected existing 补考 official type")

    final_fields, final_rows = read_csv(FINAL_REVIEW)
    targets = [
        row for row in final_rows
        if row["current_status"] == "REVIEW_REQUIRED"
        and not row["business_decision"]
        and is_resit(row["original_value"])
    ]
    if len(targets) != 18:
        raise ValueError(f"Expected 18 resit REVIEW_REQUIRED values, found {len(targets)}")
    for row in targets:
        row["suggested_official_task_type"] = RESIT
        row["confidence"] = "HIGH"
        row["mapping_reason"] = "RULE-021：补考/补考作业及明确补考或重写变体，词数、时长、essay、辅导等修饰信息不改变核心业务类型。"
        row["risk_note"] = "manual_business_confirmation：单任务补考独立于考试。"
        row["business_decision"] = "APPROVED"
        row["final_official_task_type"] = RESIT
        row["review_note"] = "manual_business_confirmation; RULE-021"

    business_fields, business_rows = read_csv(BUSINESS_REVIEW)
    update_multi = {
        "补考➕毕业论文": [RESIT, "Dissertation"],
        "补考作业+考试": [RESIT, "考试"],
    }
    for raw, components in update_multi.items():
        row = row_by_raw(business_rows, raw)
        row.update({
            "task_type_components": json.dumps(components, ensure_ascii=False),
            "unresolved_components": "[]",
            "component_mapping_status": "COMPLETE",
            "recommended_task_type_list": "|".join(components),
            "model_reason": "RULE-021：补考是独立 official task type，不再归并为考试；保留 MULTI_TASK 组件。",
            "evidence_status": "MANUAL_BUSINESS_CONFIRMATION",
            "business_decision": "APPROVED_COMPONENT_SPLIT",
            "review_note": "manual_business_confirmation; RULE-021",
        })

    audit_fields, audit_rows = read_csv(MULTI_AUDIT)
    for raw, components in update_multi.items():
        row = row_by_raw(audit_rows, raw)
        row.update({
            "task_type_components": json.dumps(components, ensure_ascii=False),
            "unresolved_components": "[]",
            "component_mapping_status": "COMPLETE",
            "evidence": "RULE-021 manual_business_confirmation：" + " | ".join(components),
            "decision": "APPROVED_COMPONENT_SPLIT",
            "review_note": "manual_business_confirmation; RULE-021",
        })

    alias_lines = [
        "# ACTIVE standalone resit aliases confirmed by business.",
        "aliases_version: \"1.0\"",
        "business_rules_version: \"11.0\"",
        "rule_id: RULE-021",
        "source: manual_business_confirmation",
        "status: ACTIVE",
        "entries:",
    ]
    for row in targets:
        alias_lines.extend([
            f"  - raw_value: {q(row['original_value'])}",
            f"    canonical_task_type: {q(RESIT)}",
            "    source: manual_business_confirmation",
            "    status: ACTIVE",
        ])
    alias_lines.append("")

    staged = [
        (stage_csv(CANONICAL, canonical_fields, canonical_rows), CANONICAL),
        (stage_csv(FINAL_REVIEW, final_fields, final_rows), FINAL_REVIEW),
        (stage_csv(BUSINESS_REVIEW, business_fields, business_rows), BUSINESS_REVIEW),
        (stage_csv(MULTI_AUDIT, audit_fields, audit_rows), MULTI_AUDIT),
        (stage_text(ALIASES, "\n".join(alias_lines)), ALIASES),
    ]
    for source, destination in staged:
        os.replace(source, destination)
    print(f"official_task_type_count={len(canonical_rows)}")
    print(f"approved_resit_single_values={len(targets)}")
    print("updated_multi_task_rows=2")


if __name__ == "__main__":
    main()
