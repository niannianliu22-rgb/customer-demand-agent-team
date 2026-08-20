#!/usr/bin/env python3
"""Create the Round-3 human finalization sheet; no dictionary or dataset writeback."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/dimension_review"
SOURCE = REVIEW_DIR / "school_ambiguous_deep_trace_round3.csv"


def main() -> None:
    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in csv.DictReader(handle):
            grouped[row["raw_value"]].append(row)
    if len(grouped) != 11:
        raise ValueError("Round-3 deep trace must contain exactly 11 review entities")

    fields = [
        "raw_value", "record_count", "current_classification", "proposed_canonical",
        "final_decision", "final_canonical", "entity_type", "review_note",
    ]
    output = []
    for raw_value, records in sorted(grouped.items()):
        item = records[0]
        status = item["resolution_status"]
        confidence = item["confidence"]
        if status == "MANUAL_CONFIRMATION_CANDIDATE":
            final_decision = ""
            entity_type = "UNIVERSITY_CANDIDATE"
            note = f"{item['evidence']} 仅为人工确认候选，未写入正式字典。"
        elif confidence == "NON_UNIVERSITY_ENTITY":
            final_decision = "NON_UNIVERSITY_ENTITY"
            entity_type = item["confidence"]
            note = f"{item['evidence']} 不作为 canonical university。"
        else:
            final_decision = "KEEP_UNRESOLVED"
            entity_type = item["confidence"]
            note = f"{item['evidence']} 保持 UNRESOLVED，不进入 canonical school dictionary。"
        output.append({
            "raw_value": raw_value,
            "record_count": len(records),
            "current_classification": (
                confidence
                if confidence == "NON_UNIVERSITY_ENTITY"
                else (confidence if status == "MANUAL_CONFIRMATION_CANDIDATE" else status)
            ),
            "proposed_canonical": item["recommended_canonical"],
            "final_decision": final_decision,
            "final_canonical": "",
            "entity_type": entity_type,
            "review_note": note,
        })
    with (REVIEW_DIR / "school_manual_finalization_round3.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)

    summary = """# School Standardization Round 3 Status

Scope: finalization preparation only. This artifact does not modify `unified_dataset.csv` or `config/data/school_aliases.yaml`.

## Status summary

| Category | Unique raw values | Business records | Treatment |
|---|---:|---:|---|
| Safe new canonical standardizations | 0 | 0 | No new canonical mapping is approved in this round. |
| Non-university classifications | 2 | 2 | `多伦多高中` and `麦唐纳国际学校` are classified as `NON_UNIVERSITY_ENTITY`; they are not canonical universities. |
| Pending human confirmation | 3 | 3 | `cmu`, `psu`, and `伯克利` have candidate mappings but no final decision. |
| Keep unresolved | 6 | 9 | `波士顿`, `维多利亚`, `UCD`, `加州大学`, `北卡`, and `华盛顿` remain `UNRESOLVED`. |

## Writeback restriction

The 12 business records represented by the three pending candidates and six unresolved values remain prohibited from canonical-school writeback. The two non-university records also remain outside university ranking and canonical-school aggregation. No Round-2 `PROPOSED_HIGH` or `PROPOSED_MEDIUM` candidate is approved by this Round-3 preparation artifact.

The existing ACTIVE dictionary is unchanged. Its 23 canonical schools remain the only formally approved canonical university entities.
"""
    (REVIEW_DIR / "school_standardization_round3_summary.md").write_text(summary, encoding="utf-8")


if __name__ == "__main__":
    main()
