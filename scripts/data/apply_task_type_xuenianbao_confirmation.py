#!/usr/bin/env python3
"""Apply the narrow, manually confirmed 学年包 task-type correction.

This intentionally edits only derived configuration/review artifacts. It never
opens for writing the company source Excel, raw source workbooks, or the
unified dataset.
"""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "runs" / "RUN-202608-DEMAND-001" / "artifacts" / "dimension_review"
CANONICAL = ROOT / "config" / "dimensions" / "task_type" / "canonical.csv"
ALIASES = ROOT / "config" / "dimensions" / "task_type" / "aliases_candidate.csv"
ROUND3 = RUN / "task_type_official_mapping_review_round3.csv"
BUSINESS_REVIEW = RUN / "task_type_business_final_review.csv"
MANUAL_ID = "MANUAL-TASK-TYPE-001"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def only(rows: list[dict[str, str]], field: str, value: str) -> dict[str, str]:
    matches = [row for row in rows if row.get(field) == value]
    if len(matches) != 1:
        raise ValueError(f"Expected one {field}={value!r}; got {len(matches)}")
    return matches[0]


def main() -> None:
    canonical_fields, canonical_rows = read_csv(CANONICAL)
    names = [row["official_order_type"] for row in canonical_rows]
    existing_manual = [
        row
        for row in canonical_rows
        if row["official_order_type"] == "学年包"
        and row["official_task_type_id"] == MANUAL_ID
        and row["official_source_record_id"] == "RULE-014"
    ]
    if "学年包" in names and len(existing_manual) != 1:
        raise ValueError("学年包 exists without the expected manual confirmation row")
    if names.count("辅导年包") != 1:
        raise ValueError("辅导年包 must exist exactly once before confirmation")
    if not existing_manual:
        canonical_rows.append(
            {
                "official_task_type_id": MANUAL_ID,
                "official_task_type_id_source": "manual_business_confirmation",
                "official_order_type": "学年包",
                "official_source_record_id": "RULE-014",
                "official_numeric_value": "",
            }
        )
        write_csv(CANONICAL, canonical_fields, canonical_rows)

    alias_fields, alias_rows = read_csv(ALIASES)
    # A failed preflight can leave this derived CSV with only its first rows.
    # Reconstruct its documented Round-3 candidate representation from the
    # authoritative Round-3 review plus the frequency artifact before making
    # the single approved correction.
    if len(alias_rows) != 210:
        round3_restore_fields, round3_restore_rows = read_csv(ROUND3)
        frequency_fields, frequency_rows = read_csv(
            RUN / "task_type_value_frequency.csv"
        )
        del round3_restore_fields, frequency_fields
        frequency_by_raw = {row["raw_value"]: row for row in frequency_rows}
        if len(round3_restore_rows) != 210 or len(frequency_by_raw) != 210:
            raise ValueError("Cannot safely reconstruct aliases_candidate.csv")
        alias_rows = []
        for row in round3_restore_rows:
            frequency = frequency_by_raw[row["raw_value"]]
            alias_rows.append(
                {
                    "raw_value": row["raw_value"],
                    "record_count": row["record_count"],
                    "proposed_official_task_type": row[
                        "proposed_official_task_type"
                    ],
                    "official_task_type_id": row["official_task_type_id"],
                    "classification": row["classification"],
                    "confidence": row["confidence"],
                    "evidence": row["evidence"],
                    "source_ids": frequency["source_ids"],
                    "years": frequency["years"],
                    "departments": frequency["departments"],
                    "approval_status": "CANDIDATE_ONLY",
                }
            )
    alias_row = only(alias_rows, "raw_value", "学年包")
    alias_row.update(
        {
            "proposed_official_task_type": "学年包",
            "official_task_type_id": MANUAL_ID,
            "classification": "EXACT_MATCH",
            "confidence": "HIGH",
            "evidence": "人工业务确认：学年包是独立官方订单类型；不得归并至辅导年包。",
        }
    )
    write_csv(ALIASES, alias_fields, alias_rows)

    round3_fields, round3_rows = read_csv(ROUND3)
    round3_row = only(round3_rows, "raw_value", "学年包")
    sample_context = round3_row["sample_context"]
    round3_row.update(
        {
            "classification": "EXACT_MATCH",
            "proposed_official_task_type": "学年包",
            "official_task_type_id": MANUAL_ID,
            "confidence": "HIGH",
            "evidence": "人工业务确认：学年包是独立官方订单类型；不得归并至辅导年包。",
        }
    )
    write_csv(ROUND3, round3_fields, round3_rows)

    review_fields, review_rows = read_csv(BUSINESS_REVIEW)
    if any(row["raw_value"] == "学年包" for row in review_rows):
        raise ValueError("学年包 already appears in business review; refusing duplicate")
    review_rows.append(
        {
            "raw_value": "学年包",
            "record_count": "21",
            "current_classification": "EXACT_MATCH",
            "proposed_official_task_type": "学年包",
            "risk_flag": "NONE",
            "original_order_type": "作业形式=学年包",
            "product_name": "NOT_AVAILABLE_IN_SOURCE",
            "service_description": "学年包",
            "customer_requirement": "NOT_REQUIRED_FOR_MANUAL_CONFIRMATION",
            "order_note": "见 sample_context",
            "sample_context": sample_context,
            "model_recommendation": "学年包",
            "model_reason": "manual_business_confirmation：学年包是独立官方订单类型，不得与辅导年包归并。",
            "evidence_status": "MANUAL_BUSINESS_CONFIRMATION",
            "recommended_primary_task_type": "",
            "recommended_task_type_list": "",
            "exception_suspected_type": "",
            "business_decision": "APPROVED",
            "final_official_task_type": "学年包",
            "review_note": "manual_business_confirmation",
        }
    )
    write_csv(BUSINESS_REVIEW, review_fields, review_rows)

    print("canonical_count", len(canonical_rows))
    print("alias_row", alias_row)
    print("round3_row", round3_row)
    print("business_review_count", len(review_rows))


if __name__ == "__main__":
    main()
