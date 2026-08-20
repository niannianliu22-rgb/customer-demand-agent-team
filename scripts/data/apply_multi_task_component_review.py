#!/usr/bin/env python3
"""Create auditable component-level results for the 20 MULTI_TASK values.

This script updates review artifacts only. It never writes raw Excel files or
the unified dataset. Components are official task types; a component not
covered by the current official list/rules is retained separately for review.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = ROOT / "runs" / "RUN-202608-DEMAND-001" / "artifacts" / "dimension_review"
BUSINESS_REVIEW = REVIEW_DIR / "task_type_business_final_review.csv"
ROUND5 = REVIEW_DIR / "task_type_multi_task_components_review_round5.csv"

# Components named here are exact values from canonical.csv. Unresolved
# components are intentionally excluded from task_type_components.
COMPONENTS: dict[str, tuple[list[str], list[str], str]] = {
    "润色＋续写": (["润色-proofreading", "essay"], [], "润色与续写（写作）"),
    "1125词+数据分析": (["essay", "Analysis"], [], "词数写作与数据分析"),
    "6k词补写+润色": (["essay", "润色-proofreading"], [], "补写（写作）与润色"),
    "LR部分润色＋续写": (["润色-proofreading", "essay"], [], "润色与续写（写作）"),
    "essay➕考试": (["essay", "考试"], [], "明确 essay 与考试"),
    "ppt+演讲稿": (["PPT", "presentation"], [], "演讲稿对应官方 presentation"),
    "ppt+考试": (["PPT", "考试"], [], "明确 PPT 与考试"),
    "quiz+answer": (["online test-exam/quiz", "做题"], [], "quiz 对应官方 online test-exam/quiz；answer 对应做题"),
    "大论文润色+补写": (["润色-proofreading", "essay"], [], "润色与补写（写作）"),
    "大论文续写+润色": (["essay", "润色-proofreading"], [], "续写（写作）与润色"),
    "实验数据+1500词report": (["Analysis", "report"], [], "实验数据分析与 report"),
    "数据收集+分析": (["Analysis"], ["数据收集"], "分析可映射；数据收集无已确认官方类型"),
    "海报+report": (["海报", "report"], [], "明确海报与 report"),
    "润色+降重+续写2000词": (["润色-proofreading", "essay"], ["降重"], "润色和续写可映射；降重无已确认官方类型"),
    "考试，作业": (["考试", "assignment"], [], "作业对应官方 assignment"),
    "补考➕毕业论文": (["Dissertation"], ["补考"], "毕业论文对应 Dissertation；补考未指明内部/外接"),
    "补考作业+考试": (["assignment", "考试"], ["补考"], "作业与考试可映射；补考未指明内部/外接"),
    "视频+海报": (["video", "海报"], [], "明确视频与海报"),
    "语言班1200词➕1.15听力考试": (["essay", "考试"], [], "词数写作与听力考试"),
    "选课+入学测试": (["选课"], ["入学测试"], "选课可映射；入学测试无已确认官方类型"),
}


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


def main() -> None:
    fields, rows = read_csv(BUSINESS_REVIEW)
    extra_fields = [
        "task_type_original",
        "task_type_mode",
        "task_type_components",
        "unresolved_components",
        "component_mapping_status",
    ]
    for field in extra_fields:
        if field not in fields:
            fields.append(field)
    multi_rows = [row for row in rows if row["current_classification"] == "MULTI_TASK"]
    if len(multi_rows) != 20:
        raise ValueError(f"Expected 20 MULTI_TASK rows; found {len(multi_rows)}")
    if set(row["raw_value"] for row in multi_rows) != set(COMPONENTS):
        raise ValueError("MULTI_TASK review values do not match controlled mapping table")

    round5_rows: list[dict[str, str]] = []
    for row in multi_rows:
        components, unresolved, rationale = COMPONENTS[row["raw_value"]]
        status = "COMPLETE" if not unresolved else "COMPONENT_REVIEW_REQUIRED"
        row.update(
            {
                "task_type_original": row["raw_value"],
                "task_type_mode": "MULTI_TASK",
                "task_type_components": json.dumps(components, ensure_ascii=False),
                "unresolved_components": json.dumps(unresolved, ensure_ascii=False),
                "component_mapping_status": status,
                "model_recommendation": "MULTI_TASK_COMPONENTS_STANDARDIZED",
                "model_reason": "RULE-016：保留 MULTI_TASK 模式，按原始顺序标准化每个可确认组件；不压缩为单一 task_type。 " + rationale,
                "evidence_status": "MANUAL_BUSINESS_CONFIRMATION" if not unresolved else "COMPONENT_REVIEW_REQUIRED",
                "business_decision": "APPROVED_COMPONENT_SPLIT" if not unresolved else "COMPONENT_REVIEW_REQUIRED",
                "final_official_task_type": "",
                "review_note": "manual_business_confirmation" if not unresolved else "official_type_or_subtype_not_confirmed",
            }
        )
        round5_rows.append(
            {
                "raw_value": row["raw_value"],
                "record_count": row["record_count"],
                "task_type_original": row["raw_value"],
                "task_type_mode": "MULTI_TASK",
                "task_type_components": json.dumps(components, ensure_ascii=False),
                "unresolved_components": json.dumps(unresolved, ensure_ascii=False),
                "component_mapping_status": status,
                "evidence": rationale,
                "sample_context": row["sample_context"],
                "decision": row["business_decision"],
                "review_note": row["review_note"],
            }
        )

    round5_fields = list(round5_rows[0])
    staged_review = stage_csv(BUSINESS_REVIEW, fields, rows)
    staged_round5 = stage_csv(ROUND5, round5_fields, round5_rows)
    os.replace(staged_review, BUSINESS_REVIEW)
    os.replace(staged_round5, ROUND5)
    print(f"multi_task_rows={len(multi_rows)}")
    print(f"complete={sum(not COMPONENTS[row['raw_value']][1] for row in multi_rows)}")
    print(f"component_review_required={sum(bool(COMPONENTS[row['raw_value']][1]) for row in multi_rows)}")


if __name__ == "__main__":
    main()
