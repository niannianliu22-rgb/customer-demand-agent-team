#!/usr/bin/env python3
"""Apply human-confirmed RULE-025 to D-group review/config artifacts only."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/dimension_review"
MAPPINGS = {
    "文献综述部分": "毕业论文半包", "2000词lr": "毕业论文半包", "5w词论文": "毕业论文半包",
    "LR修改": "毕业论文半包", "ME": "毕业论文半包", "ME部分": "毕业论文半包",
    "lr": "毕业论文半包", "me": "毕业论文半包", "文献综述": "毕业论文半包",
    "毕业论文400词": "毕业论文半包", "毕业论文浅润": "毕业论文半包", "毕业论文答辩PPT": "毕业论文半包",
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


def update_review(path: Path, value_key: str) -> int:
    fields, rows = read_csv(path)
    found = set()
    for row in rows:
        raw = row[value_key]
        if raw not in MAPPINGS:
            continue
        found.add(raw)
        row["suggested_official_task_type"] = "毕业论文半包"
        if "confidence" in row:
            row["confidence"] = "HIGH"
        if "reason" in row:
            row["reason"] = "RULE-025：按人工确认的毕业论文局部／阶段性产品服务口径映射。"
        if "ambiguity_reason" in row:
            row["ambiguity_reason"] = "已由人工业务确认消除 LR/ME/文献综述/PPT 等文本语义歧义。"
        if "mapping_reason" in row:
            row["mapping_reason"] = "RULE-025：业务产品口径优先于文本表面任务语义。"
        if "risk_note" in row:
            row["risk_note"] = "manual_business_confirmation：不按 LR/ME/文献综述/PPT 关键词拆分。"
        if "current_status" in row:
            row["current_status"] = "MANUAL_CONFIRMED_ALIAS"
        row["business_decision"] = "APPROVED"
        row["final_official_task_type"] = "毕业论文半包"
        row["review_note"] = "manual_business_confirmation; RULE-025"
    if found != set(MAPPINGS):
        raise RuntimeError(f"Missing D-group values in {path.name}: {sorted(set(MAPPINGS)-found)}")
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
        row["proposed_official_task_type"] = "毕业论文半包"
        row["risk_flag"] = "NONE"
        row["model_recommendation"] = "毕业论文半包"
        row["model_reason"] = "RULE-025：毕业论文局部／阶段性服务，业务产品口径优先于 LR/ME/文献综述/PPT 等表面语义。"
        row["evidence_status"] = "MANUAL_BUSINESS_CONFIRMATION"
        row["business_decision"] = "APPROVED"
        row["final_official_task_type"] = "毕业论文半包"
        row["review_note"] = "manual_business_confirmation; RULE-025"
    if found != set(MAPPINGS):
        raise RuntimeError(f"Missing D-group values in {path.name}: {sorted(set(MAPPINGS)-found)}")
    write_csv(path, fields, rows)
    return len(found)


def add_to_canonical() -> None:
    path = ROOT / "config/dimensions/task_type/canonical.csv"
    fields, rows = read_csv(path)
    if not any(row["official_order_type"] == "毕业论文半包" for row in rows):
        rows.append({"official_task_type_id": "MANUAL-TASK-TYPE-014", "official_task_type_id_source": "manual_business_confirmation", "official_order_type": "毕业论文半包", "official_source_record_id": "RULE-025", "official_numeric_value": ""})
        write_csv(path, fields, rows)


def write_aliases() -> None:
    path = ROOT / "config/dimensions/task_type/dissertation_partial_package_aliases.yaml"
    lines = ["# ACTIVE dissertation partial/staged-package aliases confirmed by business.", 'aliases_version: "1.0"', 'business_rules_version: "15.0"', "rule_id: RULE-025", "source: manual_business_confirmation", "status: ACTIVE", "restriction: Apply only exact listed raw values; product scope overrides LR/ME/literature/PPT surface semantics.", "entries:"]
    for raw in MAPPINGS:
        lines.extend([f'  - raw_value: "{raw}"', '    canonical_task_type: "毕业论文半包"', "    source: manual_business_confirmation", "    status: ACTIVE"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    n1 = update_review(REVIEW_DIR / "task_type_manual_final_review_v2.csv", "original_value")
    n2 = update_review(REVIEW_DIR / "task_type_review_required_reorganized.csv", "original_value")
    n3 = update_business_review(REVIEW_DIR / "task_type_business_final_review.csv")
    add_to_canonical()
    write_aliases()
    print(f"Updated {n1} manual-final, {n2} reorganized, and {n3} business-review D-group values.")


if __name__ == "__main__":
    main()
