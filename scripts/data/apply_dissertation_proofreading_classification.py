#!/usr/bin/env python3
"""Apply Rule-019 classification suggestions to risk proofreading candidates."""

from __future__ import annotations

import csv
import os
import re
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TASK_DIR = ROOT / "config" / "dimensions" / "task_type"
CANONICAL = TASK_DIR / "canonical.csv"
CLASSIFICATION_RULES = TASK_DIR / "classification_rules.yaml"
REVIEW = ROOT / "runs" / "RUN-202608-DEMAND-001" / "artifacts" / "dimension_review" / "task_type_manual_final_review_v2.csv"
NEW_TYPE = "毕业论文润色"
NEW_ID = "MANUAL-TASK-TYPE-010"


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


def parsed_word_count(raw: str) -> int | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(万|w|W)?\s*词?", raw)
    if not match:
        return None
    value = float(match.group(1))
    return int(value * 10000) if match.group(2) in {"万", "w", "W"} else int(value)


def classify(raw: str) -> tuple[str, str]:
    if any(marker.lower() in raw.lower() for marker in ("大论文润色", "毕业论文润色", "Dissertation润色")):
        return NEW_TYPE, "RULE-019 priority 1：明确毕业论文/大论文语义。"
    word_count = parsed_word_count(raw)
    if word_count is not None and word_count > 10000:
        return NEW_TYPE, f"RULE-019 priority 2：可解析词数 {word_count} > 10000。"
    return "润色-proofreading", "RULE-019 priority 3：普通润色；无明确毕业论文语义且词数不超过 10000/不可解析。"


def main() -> None:
    canonical_fields, canonical_rows = read_csv(CANONICAL)
    existing = {row["official_order_type"]: row for row in canonical_rows}
    if NEW_TYPE not in existing:
        canonical_rows.append({
            "official_task_type_id": NEW_ID,
            "official_task_type_id_source": "manual_business_confirmation",
            "official_order_type": NEW_TYPE,
            "official_source_record_id": "RULE-019",
            "official_numeric_value": "",
        })
    elif existing[NEW_TYPE]["official_task_type_id"] != NEW_ID:
        raise ValueError("Unexpected existing 毕业论文润色 canonical entry")

    review_fields, review_rows = read_csv(REVIEW)
    affected = [
        row for row in review_rows
        if row["current_status"] == "PROPOSED_HIGH"
        and row["suggested_official_task_type"] == "润色-proofreading"
    ]
    if len(affected) != 19:
        raise ValueError(f"Expected 19 risk proofreading rows, found {len(affected)}")
    changed: list[str] = []
    retained: list[str] = []
    for row in affected:
        target, reason = classify(row["original_value"])
        row["suggested_official_task_type"] = target
        row["mapping_reason"] = reason
        row["risk_note"] = "BUSINESS_SEMANTIC_RISK：已按 RULE-019 确认分类优先级更新建议；本行最终审批字段仍留空。"
        if target == NEW_TYPE:
            changed.append(row["original_value"])
        else:
            retained.append(row["original_value"])

    rule_text = """# ACTIVE task_type classification rules\nrules_version: \"9.0\"\nsource: manual_business_confirmation\nstatus: ACTIVE\nrules:\n  - rule_id: RULE-019\n    rule_name: dissertation_proofreading_classification\n    scope: task_type_single_task_classification\n    priority_order:\n      - explicit_dissertation_semantics\n      - parsed_word_count_gt_10000\n      - ordinary_proofreading\n    explicit_dissertation_markers:\n      - 大论文润色\n      - 毕业论文润色\n      - Dissertation润色\n    explicit_dissertation_target: 毕业论文润色\n    word_count_rule:\n      applies_when: raw_value_is_proofreading_service\n      comparison: \"> 10000\"\n      target: 毕业论文润色\n      equal_to_10000_uses_word_count_rule: false\n    ordinary_proofreading_target: 润色-proofreading\n    restriction: Do not infer beyond these confirmed conditions.\n    source: manual_business_confirmation\n    status: ACTIVE\n    created_at: \"2026-08-20\"\n"""
    staged_canonical = stage_csv(CANONICAL, canonical_fields, canonical_rows)
    staged_review = stage_csv(REVIEW, review_fields, review_rows)
    staged_rules = stage_text(CLASSIFICATION_RULES, rule_text)
    os.replace(staged_canonical, CANONICAL)
    os.replace(staged_review, REVIEW)
    os.replace(staged_rules, CLASSIFICATION_RULES)
    print(f"official_task_type_count={len(canonical_rows)}")
    print("affected_proofreading_rows=19")
    print("reclassified_to_dissertation_proofreading=" + "|".join(changed))
    print("retained_ordinary_proofreading=" + "|".join(retained))


if __name__ == "__main__":
    main()
