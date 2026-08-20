#!/usr/bin/env python3
"""Prepare human-review and high-confidence audit files without applying aliases."""
from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/dimension_review"


def main() -> None:
    source = REVIEW_DIR / "school_unstandardized_review_round2.csv"
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    output_fields = [
        "raw_value", "record_count", "proposed_canonical", "classification", "confidence",
        "decision", "final_canonical", "review_note",
    ]

    def project(row: dict[str, str]) -> dict[str, str]:
        return {
            "raw_value": row["original_value"],
            "record_count": row["count"],
            "proposed_canonical": row["suggested_canonical_name"],
            "classification": row["confidence"],
            "confidence": row["confidence"],
            "decision": "",
            "final_canonical": "",
            "review_note": "",
        }

    manual_rows = [project(row) for row in rows if row["confidence"] in {"REVIEW_REQUIRED", "PROPOSED_MEDIUM"}]
    high_rows = [project(row) for row in rows if row["confidence"] == "PROPOSED_HIGH"]
    for path, selected in [
        (REVIEW_DIR / "school_manual_review_round2.csv", manual_rows),
        (REVIEW_DIR / "school_proposed_high_audit.csv", high_rows),
    ]:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=output_fields)
            writer.writeheader()
            writer.writerows(selected)

    if len(manual_rows) != 34 or len(high_rows) != 67:
        raise ValueError("round-2 classification counts do not match the reviewed input")


if __name__ == "__main__":
    main()
