#!/usr/bin/env python3
"""Apply human-confirmed RULE-023 to B-group review/config artifacts only.

No raw Excel or unified dataset is read or written by this script.
"""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/dimension_review"
MAPPINGS = {
    "毕业无忧": "毕业无忧",
    "svip": "预存",
    "SVIP": "预存",
    "vip": "预存",
    "VIP": "预存",
    "安心包": "DP",
    "DP": "DP",
    "卓越安心包": "DP",
    "安心包三年": "DP",
    "半包": "包课",
    "半包课": "包课",
    "咨询包课": "包课",
    "LR部分半包": "包课",
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
        canonical = MAPPINGS[raw]
        row["suggested_official_task_type"] = canonical
        if "confidence" in row:
            row["confidence"] = "HIGH"
        if "reason" in row:
            row["reason"] = "RULE-023：按人工确认的服务包/产品业务口径映射。"
        if "ambiguity_reason" in row:
            row["ambiguity_reason"] = "已由人工业务确认消除歧义。"
        if "mapping_reason" in row:
            row["mapping_reason"] = "RULE-023：按人工确认的服务包/产品业务口径映射。"
        if "risk_note" in row:
            row["risk_note"] = "manual_business_confirmation：仅适用于 RULE-023 列明的原始值。"
        if "current_status" in row:
            row["current_status"] = "MANUAL_CONFIRMED_ALIAS"
        row["business_decision"] = "APPROVED"
        row["final_official_task_type"] = canonical
        row["review_note"] = "manual_business_confirmation; RULE-023"
    if found != set(MAPPINGS):
        raise RuntimeError(f"Missing B-group values in {path.name}: {sorted(set(MAPPINGS)-found)}")
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
        canonical = MAPPINGS[raw]
        row["current_classification"] = "MANUAL_CONFIRMED_ALIAS"
        row["proposed_official_task_type"] = canonical
        row["risk_flag"] = "NONE"
        row["model_recommendation"] = canonical
        row["model_reason"] = "RULE-023：按人工确认的服务包/产品业务口径映射。"
        row["evidence_status"] = "MANUAL_BUSINESS_CONFIRMATION"
        row["business_decision"] = "APPROVED"
        row["final_official_task_type"] = canonical
        row["review_note"] = "manual_business_confirmation; RULE-023"
    if found != set(MAPPINGS):
        raise RuntimeError(f"Missing B-group values in {path.name}: {sorted(set(MAPPINGS)-found)}")
    write_csv(path, fields, rows)
    return len(found)


def add_dp_to_canonical() -> None:
    path = ROOT / "config/dimensions/task_type/canonical.csv"
    fields, rows = read_csv(path)
    if not any(row["official_order_type"] == "DP" for row in rows):
        rows.append({
            "official_task_type_id": "MANUAL-TASK-TYPE-012",
            "official_task_type_id_source": "manual_business_confirmation",
            "official_order_type": "DP",
            "official_source_record_id": "RULE-023",
            "official_numeric_value": "",
        })
        write_csv(path, fields, rows)


def write_aliases() -> None:
    path = ROOT / "config/dimensions/task_type/service_package_aliases.yaml"
    groups = (("毕业无忧", ["毕业无忧"]), ("预存", ["svip", "SVIP", "vip", "VIP"]),
              ("DP", ["安心包", "DP", "卓越安心包", "安心包三年"]),
              ("包课", ["半包", "半包课", "咨询包课", "LR部分半包"]))
    lines = [
        "# ACTIVE service-package/product aliases confirmed by business.",
        'aliases_version: "1.0"',
        'business_rules_version: "13.0"',
        "rule_id: RULE-023",
        "source: manual_business_confirmation",
        "status: ACTIVE",
        "restriction: Apply only exact listed raw values; do not generalize to new product/package labels.",
        "entries:",
    ]
    for canonical, raw_values in groups:
        for raw in raw_values:
            lines.extend([
                f'  - raw_value: "{raw}"',
                f'    canonical_task_type: "{canonical}"',
                "    source: manual_business_confirmation",
                "    status: ACTIVE",
            ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    n1 = update_review(REVIEW_DIR / "task_type_manual_final_review_v2.csv", "original_value")
    n2 = update_review(REVIEW_DIR / "task_type_review_required_reorganized.csv", "original_value")
    n3 = update_business_review(REVIEW_DIR / "task_type_business_final_review.csv")
    add_dp_to_canonical()
    write_aliases()
    print(f"Updated {n1} manual-final, {n2} reorganized, and {n3} business-review B-group values.")


if __name__ == "__main__":
    main()
