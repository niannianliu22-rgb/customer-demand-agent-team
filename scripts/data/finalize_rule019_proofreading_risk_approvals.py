#!/usr/bin/env python3
"""Close the already manually confirmed Rule-019 risk-review rows."""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "runs" / "RUN-202608-DEMAND-001" / "artifacts" / "dimension_review" / "task_type_manual_final_review_v2.csv"
PROOFREAD_TYPES = {"润色-proofreading", "毕业论文润色"}


def main() -> None:
    with REVIEW.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    targets = [
        row for row in rows
        if row["current_status"] == "PROPOSED_HIGH"
        and row["suggested_official_task_type"] in PROOFREAD_TYPES
    ]
    if len(targets) != 19:
        raise ValueError(f"Expected 19 Rule-019 rows, found {len(targets)}")
    for row in targets:
        if row["business_decision"] not in {"", "APPROVED"}:
            raise ValueError(f"Unexpected decision for {row['original_value']}")
        row["business_decision"] = "APPROVED"
        row["final_official_task_type"] = row["suggested_official_task_type"]
        row["review_note"] = "manual_business_confirmation; RULE-019"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="", dir=REVIEW.parent, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
        staged = Path(handle.name)
    os.replace(staged, REVIEW)
    print("approved_rule019_rows=19")


if __name__ == "__main__":
    main()
