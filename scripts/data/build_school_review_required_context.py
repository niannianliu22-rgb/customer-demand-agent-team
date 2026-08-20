#!/usr/bin/env python3
"""Build source-traceable context for Round-2 school review; proposal-only."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/dimension_review"
DATASET = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/unified_dataset.csv"

# raw_value: recommendation, confidence, rationale, one-to-many risk, entity classification
ASSESSMENTS = {
    "波士顿": ("", "REVIEW_REQUIRED", "三条记录仅给出城市名，专业横跨电子商务、机械工程与计算机；无法区分 Boston University、Boston College 等。", "YES", "UNIVERSITY_UNIDENTIFIED"),
    "维多利亚": ("", "AMBIGUOUS", "两条记录的 country 分别为英国、澳洲，且没有课程代码或正式英文名；可能对应多个国家的同名院校。", "YES", "UNIVERSITY_UNIDENTIFIED"),
    "UCD": ("", "REVIEW_REQUIRED", "美国来源只能作为辅助证据；缩写可指 University of California, Davis、University College Dublin 等，记录无课程代码。", "YES", "UNIVERSITY_UNIDENTIFIED"),
    "cmu": ("Carnegie Mellon University", "PROPOSED_MEDIUM", "美国、硕士、计算机基础的组合更接近 Carnegie Mellon University；但 CMU 也可能代表其他美国院校。", "YES", "UNIVERSITY_ABBREVIATION"),
    "psu": ("Pennsylvania State University", "PROPOSED_MEDIUM", "美国、本科、心理学可支持 Penn State 候选；但 PSU 也可能代表 Portland State University 等。", "YES", "UNIVERSITY_ABBREVIATION"),
    "伯克利": ("University of California, Berkeley", "PROPOSED_MEDIUM", "美国来源与“伯克利”通常指向 UC Berkeley；但记录无校区或英文名，仍不能排除其他 Berkeley 实体。", "YES", "UNIVERSITY_ABBREVIATION"),
    "加州大学": ("", "AMBIGUOUS", "仅为 University of California 系统名称，未提供具体校区或课程代码，不能合并为单一学校。", "YES", "UNIVERSITY_SYSTEM_UNIDENTIFIED"),
    "北卡": ("", "AMBIGUOUS", "可能指 University of North Carolina 的不同校区；计算机专业不足以唯一确定校区。", "YES", "UNIVERSITY_SYSTEM_UNIDENTIFIED"),
    "华盛顿": ("", "AMBIGUOUS", "可能指 University of Washington、Washington University in St. Louis 等；金融硕士不足以唯一确定。", "YES", "UNIVERSITY_UNIDENTIFIED"),
    "多伦多高中": ("", "REVIEW_REQUIRED", "高中实体，记录未提供正式英文校名或校址；不得归入大学学校实体。", "YES", "HIGH_SCHOOL_UNIDENTIFIED"),
    "麦唐纳国际学校": ("", "REVIEW_REQUIRED", "加拿大国际学校实体，但中文译名未提供正式英文名或校址；不得与大学实体合并。", "YES", "INTERNATIONAL_SCHOOL_UNIDENTIFIED"),
}


def join_unique(rows: list[dict[str, str]], field: str) -> str:
    values = []
    for row in rows:
        value = (row.get(field) or "").strip()
        if value and value not in values:
            values.append(value)
    return " | ".join(values)


def main() -> None:
    with (REVIEW_DIR / "school_manual_review_round2.csv").open(encoding="utf-8-sig", newline="") as handle:
        review_values = {
            row["raw_value"] for row in csv.DictReader(handle) if row["classification"] == "REVIEW_REQUIRED"
        }
    if review_values != set(ASSESSMENTS):
        raise ValueError("assessment list must exactly match the current REVIEW_REQUIRED list")
    with DATASET.open(encoding="utf-8-sig", newline="") as handle:
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in csv.DictReader(handle):
            school = (row.get("school") or "").strip()
            if school in review_values:
                grouped[school].append(row)
    if set(grouped) != review_values:
        raise ValueError(f"context lookup mismatch: missing={review_values-set(grouped)}")

    fields = [
        "raw_value", "raw_value_record_count", "group_country_values", "group_degree_levels", "group_majors",
        "group_task_types", "group_consultation_dates", "group_ddl_values", "recommended_canonical", "confidence",
        "judgement_basis", "one_to_many_mapping_risk", "entity_classification", "course_name", "course_code",
        "source_id", "source_file", "source_sheet", "source_row_id", "year", "department", "country", "degree_level_original",
        "degree_level", "major", "task_type", "consultation_date_original", "consultation_date", "ddl_original", "ddl",
        "order_id", "order_status", "channel", "amount_original", "currency_original", "amount_cny", "consultant_name",
    ]
    output_rows = []
    for raw_value in sorted(grouped):
        records = grouped[raw_value]
        recommendation, confidence, basis, risk, entity_type = ASSESSMENTS[raw_value]
        shared = {
            "raw_value": raw_value,
            "raw_value_record_count": str(len(records)),
            "group_country_values": join_unique(records, "country"),
            "group_degree_levels": join_unique(records, "degree_level"),
            "group_majors": join_unique(records, "major"),
            "group_task_types": join_unique(records, "task_type"),
            "group_consultation_dates": join_unique(records, "consultation_date"),
            "group_ddl_values": join_unique(records, "ddl"),
            "recommended_canonical": recommendation,
            "confidence": confidence,
            "judgement_basis": basis,
            "one_to_many_mapping_risk": risk,
            "entity_classification": entity_type,
            # The frozen v1.0 run artifact contains no course-name/code fields.
            "course_name": "NOT_AVAILABLE_IN_UNIFIED_DATASET",
            "course_code": "NOT_AVAILABLE_IN_UNIFIED_DATASET",
        }
        for record in records:
            output_rows.append({**shared, **{field: record.get(field, "") for field in fields if field in record}})

    with (REVIEW_DIR / "school_review_required_context.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    if len(output_rows) != sum(len(records) for records in grouped.values()):
        raise ValueError("not every matching source record was output")


if __name__ == "__main__":
    main()
