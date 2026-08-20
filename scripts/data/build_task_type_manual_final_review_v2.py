#!/usr/bin/env python3
"""Build the complete, decision-empty Single Task final-review queue."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DIMENSION = ROOT / "runs" / "RUN-202608-DEMAND-001" / "artifacts" / "dimension_review"
ROUND3 = DIMENSION / "task_type_official_mapping_review_round3.csv"
ALIASES = ROOT / "config" / "dimensions" / "task_type" / "aliases_candidate.csv"
OUTPUT_CSV = DIMENSION / "task_type_manual_final_review_v2.csv"
OUTPUT_MD = DIMENSION / "task_type_manual_final_review_v2.md"

# The 25 direct-acceptance values and the manual Rule-015 aliases are outside
# this queue by explicit business instruction. MULTI_TASK/NON_TASK/UNKNOWN are
# excluded by classification below.
DIRECT_ACCEPTED = {
    "选课", "essay", "包课", "学年包", "做题", "report", "毕业论文part",
    "5000词essay", "毕业论文辅导", "ppt", "1000词essay", "800词essay", "报告",
    "海报", "1800词essay", "2700词essay", "900词essay", "cw做题", "作业essay",
    "反思", "小组pre", "海报800词", "简历", "简历制作", "试卷做题",
}
RULE_CONFIRMED = {
    "预存", "SVIP预存", "vip充值", "包课补款", "预存升级学年包定金", "毕业无忧定金",
}
RISK_EXACT = {
    "考试": "POSSIBLE_OVER_MERGE：与 online test-exam/quiz 的边界需人工确认。",
    "project": "POSSIBLE_OVER_MERGE：可能与 Team Project 或代码类 project 混合。",
    "assignment": "POSSIBLE_OVER_MERGE, SEMANTIC_CONFLICT：上下文可指做题、essay 或其他作业。",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def review_required_group(raw: str) -> str:
    if "补考" in raw or "重写" in raw:
        return "B1. 补考/重写类"
    if any(token in raw for token in ("包课", "年包", "无忧", "套餐", "服务包")):
        return "B2. 服务包类"
    if any(token in raw.lower() for token in ("质检", "check", "检测")):
        return "B3. 质检类"
    if any(token in raw.lower() for token in ("论文", "大论文", "lr", "me", "part", "文献综述")):
        return "B4. 论文部分/缩写类"
    if re.fullmatch(r"[0-9.]+(?:[wkW万千]?[词字])?", raw.strip()):
        return "B5. 仅字数/信息不足类"
    return "B6. 其他无法唯一映射类"


def risk_note(row: dict[str, str]) -> str:
    raw = row["raw_value"]
    status = row["classification"]
    if status == "EXACT_MATCH":
        return RISK_EXACT[raw]
    if row["proposed_official_task_type"] == "润色-proofreading":
        return "POSSIBLE_WRONG_MAPPING：润色服务可能涉及 revision、降重或补写，需业务确认。"
    if row["proposed_official_task_type"] == "Dissertation":
        return "POSSIBLE_OVER_MERGE：可能是完整论文、部分论文、辅导或其他论文服务。"
    if row["proposed_official_task_type"] == "code/experiment":
        return "POSSIBLE_OVER_MERGE：代码、实验与其他技术服务边界需确认。"
    return "风险聚类：需人工确认。"


def main() -> None:
    round3_rows = read_csv(ROUND3)
    aliases = {row["raw_value"]: row for row in read_csv(ALIASES)}
    rows: list[dict[str, str]] = []
    for row in round3_rows:
        raw = row["raw_value"]
        status = row["classification"]
        if raw in DIRECT_ACCEPTED or raw in RULE_CONFIRMED:
            continue
        if status not in {"PROPOSED_MEDIUM", "REVIEW_REQUIRED", "PROPOSED_HIGH", "EXACT_MATCH"}:
            continue
        # All remaining high-confidence candidates are in a documented risk
        # cluster; include them so the queue is genuinely exhaustive.
        alias = aliases.get(raw)
        if alias is None:
            raise ValueError(f"Missing source coverage for {raw!r}")
        if status == "PROPOSED_MEDIUM":
            group = "A. PROPOSED_MEDIUM"
            note = "需人工确认建议类型，尚未批准。"
        elif status == "REVIEW_REQUIRED":
            group = review_required_group(raw)
            note = "现有规则无法唯一映射。"
        elif status == "EXACT_MATCH":
            group = "C1. 风险 EXACT_MATCH"
            note = risk_note(row)
        else:
            group = "C2. 风险 PROPOSED_HIGH"
            note = risk_note(row)
        rows.append(
            {
                "review_group": group,
                "original_value": raw,
                "count": row["record_count"],
                "current_status": status,
                "suggested_official_task_type": row["proposed_official_task_type"],
                "confidence": row["confidence"],
                "mapping_reason": row["evidence"],
                "source_ids": alias["source_ids"],
                "risk_note": note,
                "business_decision": "",
                "final_official_task_type": "",
                "review_note": "",
            }
        )
    expected = {"PROPOSED_MEDIUM": 41, "REVIEW_REQUIRED": 88, "EXACT_MATCH": 3, "PROPOSED_HIGH": 25}
    actual = defaultdict(int)
    for row in rows:
        actual[row["current_status"]] += 1
    if dict(actual) != expected:
        raise ValueError(f"Unexpected queue composition: {dict(actual)}")
    group_order = {
        "A. PROPOSED_MEDIUM": 1,
        "B1. 补考/重写类": 2,
        "B2. 服务包类": 3,
        "B3. 质检类": 4,
        "B4. 论文部分/缩写类": 5,
        "B5. 仅字数/信息不足类": 6,
        "B6. 其他无法唯一映射类": 7,
        "C1. 风险 EXACT_MATCH": 8,
        "C2. 风险 PROPOSED_HIGH": 9,
    }
    rows.sort(key=lambda r: (group_order[r["review_group"]], r["suggested_official_task_type"], -int(r["count"]), r["original_value"]))
    for index, row in enumerate(rows, 1):
        row["review_id"] = f"TT-FINAL-V2-{index:03d}"
    field_order = [
        "review_id", "original_value", "count", "current_status",
        "suggested_official_task_type", "confidence", "mapping_reason", "source_ids",
        "risk_note", "business_decision", "final_official_task_type", "review_note",
    ]
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_order, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["review_group"]].append(row)
    lines = [
        "# Task Type 人工最终审核清单 V2",
        "",
        "本清单仅组织尚未最终人工确认的单任务原始值。`business_decision`、`final_official_task_type` 与 `review_note` 均保持空白。",
        "",
        f"- 待审原始值：{len(rows)}",
        f"- 涉及记录：{sum(int(row['count']) for row in rows)}",
        "- 已排除：25 条直接接受项、20 条已完成 MULTI_TASK、已确认 NON_TASK/UNKNOWN 映射、以及已写入 ACTIVE Business Rules 的值。",
        "",
    ]
    for group in sorted(groups, key=lambda name: group_order[name]):
        lines.extend([f"## {group}（{len(groups[group])} 个原始值）", "", "| 原始值 | 数量 | 当前状态 | 建议类型 | 置信度 | 原因 | 风险备注 |", "|---|---:|---|---|---|---|---|"])
        for row in groups[group]:
            reason = row["mapping_reason"].replace("|", "\\|")
            note = row["risk_note"].replace("|", "\\|")
            lines.append(f"| {row['original_value']} | {row['count']} | {row['current_status']} | {row['suggested_official_task_type'] or '—'} | {row['confidence']} | {reason} | {note} |")
        lines.append("")
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"pending_values={len(rows)}")
    print(f"records={sum(int(row['count']) for row in rows)}")
    print("status_counts=" + ", ".join(f"{key}:{actual[key]}" for key in sorted(actual)))
    print("review_groups=" + ", ".join(f"{key}:{len(groups[key])}" for key in sorted(groups, key=lambda name: group_order[name])))


if __name__ == "__main__":
    main()
