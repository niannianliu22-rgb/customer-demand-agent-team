"""Create a human-decision CSV from school inventory and proposed aliases only."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIELDS = [
    "candidate_group_id", "original_value", "count", "source_ids", "years", "departments",
    "country_values", "suggested_canonical_name", "confidence", "current_status",
    "human_decision", "human_canonical_name", "human_notes",
]
NON_SCHOOL = [
    ("SCH-NON-SCHOOL-001", "/", "Non-school placeholder / unknown entry", "REVIEW_REQUIRED"),
    ("SCH-NON-SCHOOL-002", "未知", "Non-school unknown value", "REVIEW_REQUIRED"),
]


def serial(values):
    return " | ".join(str(value) for value in values)


def main(run_id: str):
    out_dir = ROOT / "runs" / run_id / "artifacts" / "dimension_review"
    inventory = json.loads((out_dir / "school_value_inventory.json").read_text(encoding="utf-8"))
    candidates = json.loads((out_dir / "school_alias_candidates.json").read_text(encoding="utf-8"))
    lookup = {item["original_value"]: item for item in inventory["values"]}
    rows = []
    for group in candidates["groups"]:
        for original_value in group["original_values"]:
            item = lookup[original_value]
            rows.append({
                "candidate_group_id": group["candidate_group_id"],
                "original_value": original_value,
                "count": item["count"],
                "source_ids": serial(item["source_ids"]),
                "years": serial(item["years"]),
                "departments": serial(item["departments"]),
                "country_values": serial(item["country_values"]),
                "suggested_canonical_name": group["suggested_canonical_name"] or "",
                "confidence": group["confidence"],
                "current_status": group["status"],
                "human_decision": "",
                "human_canonical_name": "",
                "human_notes": "",
            })
    for group_id, original_value, suggestion, status in NON_SCHOOL:
        item = lookup[original_value]
        rows.append({
            "candidate_group_id": group_id, "original_value": original_value, "count": item["count"],
            "source_ids": serial(item["source_ids"]), "years": serial(item["years"]),
            "departments": serial(item["departments"]), "country_values": serial(item["country_values"]),
            "suggested_canonical_name": suggestion, "confidence": "REVIEW_REQUIRED", "current_status": status,
            "human_decision": "", "human_canonical_name": "", "human_notes": "",
        })
    rows.sort(key=lambda row: (row["candidate_group_id"], row["original_value"]))
    with (out_dir / "school_alias_review.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"candidate_group_count": len(candidates["groups"]) + len(NON_SCHOOL), "review_rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "RUN-202608-DEMAND-001")
