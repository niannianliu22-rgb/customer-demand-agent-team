#!/usr/bin/env python3
"""Inventory and conservatively classify task_type values; proposal-only."""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/unified_dataset.csv"
OUT = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/dimension_review"


EXACT = {
    "选课": ("COURSE_SELECTION", "ACADEMIC_ADMINISTRATION"),
    "essay": ("ESSAY", "WRITTEN_ASSIGNMENT"),
    "毕业论文": ("DISSERTATION", "DISSERTATION"),
    "补考": ("RESIT_EXAM", "EXAMINATION"),
    "考试": ("EXAM", "EXAMINATION"),
    "辅导": ("TUTORING", "TUTORING"),
    "包课": ("COURSE_PACKAGE", "SERVICE_PACKAGE"),
    "作业": ("ASSIGNMENT", "WRITTEN_ASSIGNMENT"),
    "学年包": ("ACADEMIC_YEAR_PACKAGE", "SERVICE_PACKAGE"),
    "预存": ("PREPAID_CREDIT", "COMMERCIAL_TRANSACTION"),
    "做题": ("PROBLEM_SOLVING", "ACADEMIC_EXERCISE"),
    "润色": ("PROOFREADING", "WRITING_SUPPORT"),
    "quiz": ("QUIZ", "EXAMINATION"),
    "report": ("REPORT", "WRITTEN_ASSIGNMENT"),
    "project": ("PROJECT", "PROJECT_WORK"),
    "ppt": ("PRESENTATION", "PRESENTATION"),
    "简历": ("RESUME", "CAREER_DOCUMENT"),
    "面试": ("INTERVIEW", "CAREER_SUPPORT"),
    "质检": ("QUALITY_CHECK", "QUALITY_ASSURANCE"),
    "毕业无忧": ("GRADUATION_SUPPORT_PACKAGE", "SERVICE_PACKAGE"),
    "安心包": ("ASSURANCE_PACKAGE", "SERVICE_PACKAGE"),
    "卓越安心包": ("PREMIUM_ASSURANCE_PACKAGE", "SERVICE_PACKAGE"),
    "svip": ("SVIP_PACKAGE", "SERVICE_PACKAGE"),
    "vip": ("VIP_PACKAGE", "SERVICE_PACKAGE"),
}


def classify(raw: str) -> tuple[str, str, str, str, str, bool]:
    """Return canonical, group, classification, confidence, reasoning, multi."""
    value = raw.strip()
    normalized = value.lower().replace(" ", "")
    if not value:
        return "", "", "UNKNOWN", "UNKNOWN", "空值，未提供任务信息。", False
    if value == "/":
        return "", "", "UNKNOWN", "UNKNOWN", "占位符“/”，未提供任务信息。", False
    if normalized in EXACT:
        canonical, group = EXACT[normalized]
        return canonical, group, "STANDARDIZED", "HIGH", "与已有通用任务名称精确一致；本轮仅作为候选标准。", False
    # Explicit combinations must not be collapsed into one task type.
    if any(token in value for token in ("+", "＋", "➕", "，")):
        return "", "", "REVIEW_REQUIRED", "MULTI_TASK", "包含多个任务/交付物语义，禁止压缩为单一 task_type。", True
    if normalized in {"vip充值", "svip预存", "毕业无忧定金", "包课补款"}:
        return "", "", "NON_TASK", "HIGH", "充值、定金或补款属于交易动作，不是服务任务类型。", False
    if normalized in {"中外合办", "高中", "语言班"}:
        return "", "", "NON_TASK", "HIGH", "教育背景/课程阶段，不是具体任务类型。", False
    if normalized in {"dp", "4500", "题目", "总结"}:
        return "", "", "REVIEW_REQUIRED", "LOW", "值缺少可唯一识别的任务语义。", False
    if normalized in {"lr", "me", "cw", "unity", "实验", "反思", "采访稿", "毕业影集", "网课"}:
        return "", "", "PROPOSED_MEDIUM", "MEDIUM", "可能代表学术文档、课程或交付物，但缩写/语义不足以固定唯一口径。", False
    if normalized == "论文":
        return "PAPER", "WRITTEN_ASSIGNMENT", "PROPOSED_MEDIUM", "MEDIUM", "“论文”可能是课程论文或学位论文，不能与毕业论文强制合并。", False
    if normalized.startswith("毕业设计") or normalized.startswith("毕设"):
        return "CAPSTONE_PROJECT", "CAPSTONE", "PROPOSED_HIGH", "HIGH", "毕业设计/毕设为明确的项目类任务。", False
    if "毕业论文" in value or "大论文" in value:
        if "润色" in value or "浅润" in value or "深润" in value:
            return "DISSERTATION_PROOFREADING", "DISSERTATION", "PROPOSED_HIGH", "HIGH", "明确包含学位论文与润色服务语义。", False
        if "数据" in value:
            return "DISSERTATION_DATA_ANALYSIS", "DISSERTATION", "PROPOSED_HIGH", "HIGH", "明确包含学位论文与数据工作语义。", False
        if "辅导" in value:
            return "DISSERTATION_TUTORING", "DISSERTATION", "PROPOSED_HIGH", "HIGH", "明确包含学位论文与辅导语义。", False
        if "part" in normalized or "部分" in value or "me" in normalized or "lr" in normalized:
            return "DISSERTATION_COMPONENT", "DISSERTATION", "PROPOSED_MEDIUM", "MEDIUM", "仅指论文部分/缩写，需确认具体交付类型。", False
        if "续写" in value or "补写" in value:
            return "DISSERTATION_WRITING", "DISSERTATION", "PROPOSED_HIGH", "HIGH", "明确的学位论文写作/续写语义。", False
        if "质检" in value:
            return "DISSERTATION_QUALITY_CHECK", "DISSERTATION", "PROPOSED_HIGH", "HIGH", "明确的学位论文质检语义。", False
        return "DISSERTATION", "DISSERTATION", "PROPOSED_HIGH", "HIGH", "包含明确的毕业论文/大论文语义。", False
    if "补考" in value:
        return "RESIT_EXAM", "EXAMINATION", "PROPOSED_HIGH", "HIGH", "包含明确补考语义；时长/字数作为辅助描述保留在原值。", False
    if "考试" in value or normalized.endswith("考"):
        return "EXAM", "EXAMINATION", "PROPOSED_HIGH", "HIGH", "包含明确考试语义；时长/线上线下作为辅助描述保留在原值。", False
    if "essay" in normalized:
        return "ESSAY", "WRITTEN_ASSIGNMENT", "PROPOSED_HIGH", "HIGH", "包含 essay 语义；字数/重写等描述不改变主任务类型。", False
    if "润色" in value or "浅润" in value or "深润" in value or "修改" in value:
        return "PROOFREADING", "WRITING_SUPPORT", "PROPOSED_HIGH", "HIGH", "包含明确润色/修改服务语义。", False
    if "论文" in value:
        return "PAPER", "WRITTEN_ASSIGNMENT", "PROPOSED_MEDIUM", "MEDIUM", "包含论文语义，但未说明课程论文或学位论文。", False
    if "词" in normalized:
        return "", "", "REVIEW_REQUIRED", "LOW", "仅含字数，未表达任务类型。", False
    if "ppt" in normalized or "pre" in normalized or "演讲稿" in value:
        return "PRESENTATION", "PRESENTATION", "PROPOSED_HIGH", "HIGH", "包含演示文稿/展示语义。", False
    if "海报" in value:
        return "POSTER", "PRESENTATION", "PROPOSED_HIGH", "HIGH", "包含海报交付物语义。", False
    if "简历" in value:
        return "RESUME", "CAREER_DOCUMENT", "PROPOSED_HIGH", "HIGH", "包含简历交付物语义。", False
    if "代码" in value or "matlab" in normalized or "编程" in value:
        return "CODING_ASSIGNMENT", "PROGRAMMING", "PROPOSED_HIGH", "HIGH", "包含代码/编程交付物语义。", False
    if "网站制作" in value:
        return "WEBSITE_DEVELOPMENT", "PROGRAMMING", "PROPOSED_HIGH", "HIGH", "明确网站制作任务。", False
    if "数据" in value:
        return "DATA_ANALYSIS", "DATA_WORK", "PROPOSED_MEDIUM", "MEDIUM", "数据相关任务需区分收集、分析或论文组成部分。", False
    if "选课" in value:
        return "COURSE_SELECTION", "ACADEMIC_ADMINISTRATION", "PROPOSED_HIGH", "HIGH", "包含选课语义。", False
    if "作业" in value or "assignment" in normalized:
        return "ASSIGNMENT", "WRITTEN_ASSIGNMENT", "PROPOSED_HIGH", "HIGH", "包含明确作业语义。", False
    if "做题" in value or "试卷" in value:
        return "PROBLEM_SOLVING", "ACADEMIC_EXERCISE", "PROPOSED_HIGH", "HIGH", "包含做题/试卷语义。", False
    if "重修" in value:
        return "COURSE_RETAKE", "ACADEMIC_ADMINISTRATION", "PROPOSED_HIGH", "HIGH", "明确重修课程语义。", False
    if "半包" in value:
        return "PARTIAL_COURSE_PACKAGE", "SERVICE_PACKAGE", "PROPOSED_HIGH", "HIGH", "明确半包课/部分服务包语义。", False
    return "", "", "REVIEW_REQUIRED", "LOW", "无可复用且可验证的任务标准化规则，需人工确认。", False


def main() -> None:
    with DATASET.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    stats = defaultdict(lambda: {"count": 0, "source_ids": set(), "years": set(), "departments": set()})
    for row in rows:
        raw = (row.get("task_type") or "").strip()
        stat = stats[raw]
        stat["count"] += 1; stat["source_ids"].add(row["source_id"]); stat["years"].add(row["year"]); stat["departments"].add(row["department"])
    OUT.mkdir(parents=True, exist_ok=True)
    frequency_path = OUT / "task_type_value_frequency.csv"
    with frequency_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["raw_value","record_count","source_ids","years","departments"])
        writer.writeheader()
        for raw, stat in sorted(stats.items(), key=lambda item: (-item[1]["count"], item[0])):
            writer.writerow({"raw_value":raw,"record_count":stat["count"],"source_ids":"|".join(sorted(stat["source_ids"])),"years":"|".join(sorted(stat["years"])),"departments":"|".join(sorted(stat["departments"]))})
    review = []
    class_counts = Counter(); multi_count = 0
    for raw, stat in sorted(stats.items(), key=lambda item: (-item[1]["count"], item[0])):
        canonical, group, classification, confidence, reasoning, multi = classify(raw)
        class_counts[classification] += 1; multi_count += multi
        review.append({"raw_value":raw,"record_count":stat["count"],"source_ids":"|".join(sorted(stat["source_ids"])),"years":"|".join(sorted(stat["years"])),"departments":"|".join(sorted(stat["departments"])),"proposed_canonical_task_type":canonical,"proposed_task_type_group":group,"classification":classification,"confidence":confidence,"is_multi_task":"MULTI_TASK" if multi else "NO","reasoning":reasoning,"human_decision":"","human_canonical_task_type":"","human_notes":""})
    review_path = OUT / "task_type_unstandardized_review_round1.csv"
    fieldnames = list(review[0])
    with review_path.open("w", encoding="utf-8", newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fieldnames); writer.writeheader(); writer.writerows(review)
    summary = f"""# Task Type Standardization — Round 1 Summary

Input: `runs/RUN-202608-DEMAND-001/artifacts/unified_dataset.csv` (818 records).

## Dictionary check

No formal ACTIVE task_type canonical dictionary or task_type alias mapping was found in the project. RULE-008 defines only field-level equivalence (`作业形式` / `作业类型` / `咨询内容` → `task_type`); it does not authorize value-level recategorization. Therefore this round is `PROPOSED_ONLY`.

## Inventory and classification (unique raw values)

| Metric | Unique values |
|---|---:|
| Unique raw values, including blank | {len(stats)} |
| Unique non-empty raw values | {sum(bool(value) for value in stats)} |
| STANDARDIZED | {class_counts['STANDARDIZED']} |
| PROPOSED_HIGH | {class_counts['PROPOSED_HIGH']} |
| PROPOSED_MEDIUM | {class_counts['PROPOSED_MEDIUM']} |
| REVIEW_REQUIRED | {class_counts['REVIEW_REQUIRED']} |
| NON_TASK | {class_counts['NON_TASK']} |
| UNKNOWN | {class_counts['UNKNOWN']} |
| MULTI_TASK flag | {multi_count} |

The review CSV contains every raw value, source coverage, proposed canonical task type/group, conservative confidence, and blank human-decision columns. No dataset or dictionary was modified.
"""
    (OUT / "task_type_standardization_round1_summary.md").write_text(summary, encoding="utf-8")
    if len(review) != len(stats) or sum(stat["count"] for stat in stats.values()) != len(rows):
        raise ValueError("frequency inventory is incomplete")


if __name__ == "__main__": main()
