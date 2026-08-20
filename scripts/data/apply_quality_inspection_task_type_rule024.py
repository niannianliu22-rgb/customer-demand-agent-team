#!/usr/bin/env python3
"""Apply human-confirmed RULE-024 to C-group review/config artifacts only."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/dimension_review"
MAPPINGS = {"质检": "质检", "毕业论文质检": "质检", "论文质检": "质检"}


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
        row["suggested_official_task_type"] = "质检"
        if "confidence" in row:
            row["confidence"] = "HIGH"
        if "reason" in row:
            row["reason"] = "RULE-024：按人工确认的质检业务口径统一映射。"
        if "ambiguity_reason" in row:
            row["ambiguity_reason"] = "已由人工业务确认消除高级／普通及论文语义歧义。"
        if "mapping_reason" in row:
            row["mapping_reason"] = "RULE-024：按人工确认的质检业务口径统一映射。"
        if "risk_note" in row:
            row["risk_note"] = "manual_business_confirmation：不按原始备注或论文语义拆分等级。"
        if "current_status" in row:
            row["current_status"] = "MANUAL_CONFIRMED_ALIAS"
        row["business_decision"] = "APPROVED"
        row["final_official_task_type"] = "质检"
        row["review_note"] = "manual_business_confirmation; RULE-024"
    if found != set(MAPPINGS):
        raise RuntimeError(f"Missing C-group values in {path.name}: {sorted(set(MAPPINGS)-found)}")
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
        row["proposed_official_task_type"] = "质检"
        row["risk_flag"] = "NONE"
        row["model_recommendation"] = "质检"
        row["model_reason"] = "RULE-024：按人工确认的质检业务口径统一映射；不再拆分高级／普通。"
        row["evidence_status"] = "MANUAL_BUSINESS_CONFIRMATION"
        row["business_decision"] = "APPROVED"
        row["final_official_task_type"] = "质检"
        row["review_note"] = "manual_business_confirmation; RULE-024"
    if found != set(MAPPINGS):
        raise RuntimeError(f"Missing C-group values in {path.name}: {sorted(set(MAPPINGS)-found)}")
    write_csv(path, fields, rows)
    return len(found)


def add_quality_to_canonical() -> None:
    path = ROOT / "config/dimensions/task_type/canonical.csv"
    fields, rows = read_csv(path)
    if not any(row["official_order_type"] == "质检" for row in rows):
        rows.append({
            "official_task_type_id": "MANUAL-TASK-TYPE-013",
            "official_task_type_id_source": "manual_business_confirmation",
            "official_order_type": "质检",
            "official_source_record_id": "RULE-024",
            "official_numeric_value": "",
        })
        write_csv(path, fields, rows)


def write_aliases() -> None:
    path = ROOT / "config/dimensions/task_type/quality_inspection_aliases.yaml"
    lines = [
        "# ACTIVE quality-inspection aliases confirmed by business.",
        'aliases_version: "1.0"',
        'business_rules_version: "14.0"',
        "rule_id: RULE-024",
        "source: manual_business_confirmation",
        "status: ACTIVE",
        "restriction: Apply only exact listed raw values. Do not split by 高级/普通 or paper semantics.",
        "entries:",
    ]
    for raw in MAPPINGS:
        lines.extend([
            f'  - raw_value: "{raw}"',
            '    canonical_task_type: "质检"',
            "    source: manual_business_confirmation",
            "    status: ACTIVE",
        ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    n1 = update_review(REVIEW_DIR / "task_type_manual_final_review_v2.csv", "original_value")
    n2 = update_review(REVIEW_DIR / "task_type_review_required_reorganized.csv", "original_value")
    n3 = update_business_review(REVIEW_DIR / "task_type_business_final_review.csv")
    add_quality_to_canonical()
    write_aliases()
    print(f"Updated {n1} manual-final, {n2} reorganized, and {n3} business-review C-group values.")


if __name__ == "__main__":
    main()
