#!/usr/bin/env python3
"""Apply six narrow manual task-type confirmations and retain two UNKNOWNs.

No source workbook or unified dataset is opened for writing.  CSV updates are
staged to temporary files and atomically replaced only after all validations.
"""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "config" / "dimensions" / "task_type" / "canonical.csv"
REVIEW = (
    ROOT
    / "runs"
    / "RUN-202608-DEMAND-001"
    / "artifacts"
    / "dimension_review"
    / "task_type_business_final_review.csv"
)

CONFIRMED = {
    "预存": ("预存", "MANUAL-TASK-TYPE-002"),
    "SVIP预存": ("预存", "MANUAL-TASK-TYPE-002"),
    "vip充值": ("预存", "MANUAL-TASK-TYPE-002"),
    "包课补款": ("包课", "5"),
    "预存升级学年包定金": ("学年包", "MANUAL-TASK-TYPE-001"),
    "毕业无忧定金": ("毕业无忧", "MANUAL-TASK-TYPE-003"),
}
UNKNOWN_VALUES = {"/", ""}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def stage_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> Path:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8-sig", newline="", dir=path.parent, delete=False
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
        return Path(handle.name)


def unique(rows: list[dict[str, str]], raw_value: str) -> dict[str, str]:
    found = [row for row in rows if row["raw_value"] == raw_value]
    if len(found) != 1:
        raise ValueError(f"Expected exactly one review row for {raw_value!r}; got {len(found)}")
    return found[0]


def main() -> None:
    canonical_fields, canonical_rows = read_csv(CANONICAL)
    existing = {row["official_order_type"]: row for row in canonical_rows}
    for expected in ("包课", "学年包", "辅导年包"):
        if expected not in existing:
            raise ValueError(f"Required official task type missing: {expected}")
    additions = [
        ("预存", "MANUAL-TASK-TYPE-002"),
        ("毕业无忧", "MANUAL-TASK-TYPE-003"),
    ]
    for name, identifier in additions:
        if name in existing:
            if existing[name]["official_task_type_id"] != identifier:
                raise ValueError(f"Unexpected existing official row for {name}")
            continue
        canonical_rows.append(
            {
                "official_task_type_id": identifier,
                "official_task_type_id_source": "manual_business_confirmation",
                "official_order_type": name,
                "official_source_record_id": "RULE-015",
                "official_numeric_value": "",
            }
        )

    review_fields, review_rows = read_csv(REVIEW)
    for raw_value, (canonical, _identifier) in CONFIRMED.items():
        row = unique(review_rows, raw_value)
        if row["current_classification"] not in {"NON_TASK", "MANUAL_CONFIRMED_ALIAS"}:
            raise ValueError(f"Unexpected prior classification for {raw_value}: {row['current_classification']}")
        row.update(
            {
                "current_classification": "MANUAL_CONFIRMED_ALIAS",
                "proposed_official_task_type": canonical,
                "model_recommendation": canonical,
                "model_reason": "manual_business_confirmation：业务实质优先于支付动作文本；仅按 RULE-015 的明确映射执行，不得泛化。",
                "evidence_status": "MANUAL_BUSINESS_CONFIRMATION",
                "exception_suspected_type": "",
                "business_decision": "APPROVED",
                "final_official_task_type": canonical,
                "review_note": "manual_business_confirmation",
            }
        )
    for raw_value in UNKNOWN_VALUES:
        row = unique(review_rows, raw_value)
        if row["current_classification"] != "UNKNOWN":
            raise ValueError(f"Unexpected prior classification for UNKNOWN {raw_value!r}")
        row.update(
            {
                "proposed_official_task_type": "",
                "model_recommendation": "KEEP_UNKNOWN",
                "model_reason": "manual_business_confirmation：原始值未表达可确认的任务类型，不得推测。",
                "evidence_status": "MANUAL_BUSINESS_CONFIRMATION",
                "business_decision": "KEEP_UNKNOWN",
                "final_official_task_type": "",
                "review_note": "manual_business_confirmation",
            }
        )

    staged_canonical = stage_csv(CANONICAL, canonical_fields, canonical_rows)
    staged_review = stage_csv(REVIEW, review_fields, review_rows)
    os.replace(staged_canonical, CANONICAL)
    os.replace(staged_review, REVIEW)
    print(f"official_task_type_count={len(canonical_rows)}")
    print("confirmed_alias_count=6")
    print("unknown_count=2")


if __name__ == "__main__":
    main()
