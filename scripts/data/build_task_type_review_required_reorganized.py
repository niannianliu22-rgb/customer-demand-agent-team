#!/usr/bin/env python3
"""Reorganize the true remaining REVIEW_REQUIRED task-type queue for humans."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DIMENSION = ROOT / "runs" / "RUN-202608-DEMAND-001" / "artifacts" / "dimension_review"
SOURCE = DIMENSION / "task_type_manual_final_review_v2.csv"
OUTPUT_CSV = DIMENSION / "task_type_review_required_reorganized.csv"
OUTPUT_MD = DIMENSION / "task_type_review_required_reorganized.md"


def group(raw: str) -> tuple[str, str, str, str]:
    if "补考" in raw or "重写" in raw:
        return (
            "A. 补考 / 重写类",
            "补考/重写-内部 或 补考/重写-外接（待确认）",
            "原始值表达补考或重写需求。",
            "尚不清楚“补考/重写”是任务类型、业务属性，还是内部/外接归属；现有规则仅覆盖 MULTI_TASK，不覆盖此单任务值。",
        )
    if any(token.lower() in raw.lower() for token in ("包课", "无忧", "svip", "vip", "安心包", "卓越", "dp", "半包")):
        return (
            "B. 服务包 / 产品类",
            "",
            "原始值更像服务包、会员或产品名称。",
            "无法仅凭产品名称确认其对应的具体订单任务类型或是否应作为独立产品维度。",
        )
    if "质检" in raw:
        return (
            "C. 质检类",
            "高级质检 或 普通质检（待确认）",
            "原始值明确为质检服务。",
            "当前缺少高级/普通质检的判别条件，且可能与论文/交付物类型同时存在。",
        )
    if any(token.lower() in raw.lower() for token in ("论文", "文献", "lr", "me", "答辩")):
        return (
            "D. 论文部分 / 缩写类",
            "",
            "原始值涉及论文整体、部分、缩写或论文附属交付物。",
            "可能对应 Dissertation、Dissertation-part、Analysis、毕业论文润色或其他类型，现有证据不足以唯一确定。",
        )
    if re.fullmatch(r"\s*(?:[0-9.]+\s*(?:[kKwW万]?)\s*(?:词)?|[一二三四五六七八九十两]+千?词)\s*", raw) or re.fullmatch(r"\d+\s*-\s*\d+\s*词", raw):
        return (
            "E. 仅字数或信息不足类",
            "",
            "原始值仅提供词数/数量，没有任务语义。",
            "不能从词数推断 essay、report、润色或其他正式类型。",
        )
    return (
        "F. 其他无法唯一映射类",
        "",
        "原始值提供了有限业务线索。",
        "缺少可唯一映射到现有 official task type 的 ACTIVE 业务规则或上下文证据。",
    )


def main() -> None:
    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    rows = [
        row for row in source_rows
        if row["current_status"] == "REVIEW_REQUIRED"
        and not row["business_decision"]
        and not row["final_official_task_type"]
    ]
    # The active rules explicitly do not auto-map REVIEW_REQUIRED values; this
    # recomputation uses current decisions rather than the historical counter.
    if not rows:
        raise ValueError("No unresolved REVIEW_REQUIRED rows found")
    output: list[dict[str, str]] = []
    for row in rows:
        review_group, suggestion, reason, ambiguity = group(row["original_value"])
        output.append(
            {
                "review_group": review_group,
                "original_value": row["original_value"],
                "count": row["count"],
                "source_ids": row["source_ids"],
                "suggested_official_task_type": suggestion,
                "confidence": "LOW",
                "reason": reason,
                "ambiguity_reason": ambiguity,
                "current_status": "REVIEW_REQUIRED",
                "business_decision": "",
                "final_official_task_type": "",
                "review_note": "",
            }
        )
    order = {
        "A. 补考 / 重写类": 1, "B. 服务包 / 产品类": 2, "C. 质检类": 3,
        "D. 论文部分 / 缩写类": 4, "E. 仅字数或信息不足类": 5,
        "F. 其他无法唯一映射类": 6,
    }
    output.sort(key=lambda row: (order[row["review_group"]], -int(row["count"]), row["original_value"]))
    fields = list(output[0])
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(output)

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in output:
        grouped[row["review_group"]].append(row)
    lines = [
        "# Task Type REVIEW_REQUIRED 人工审核重整",
        "",
        "此清单基于最新最终审核 Artifact 与 ACTIVE Business Rules v10.0 重新计算。所有决策字段均为空，未进行自动批准。",
        "",
        f"- 真实未决原始值：{len(output)}",
        f"- 涉及业务记录：{sum(int(row['count']) for row in output)}",
        "",
    ]
    for category in sorted(grouped, key=lambda value: order[value]):
        group_rows = grouped[category]
        lines.extend([f"## {category}（{len(group_rows)} 个原始值 / {sum(int(row['count']) for row in group_rows)} 条记录）", "", "| 原始值 | 数量 | 建议类型 | 为什么这样建议 | 为什么仍需人工确认 |", "|---|---:|---|---|---|"])
        for row in group_rows:
            lines.append(f"| {row['original_value']} | {row['count']} | {row['suggested_official_task_type'] or '—'} | {row['reason']} | {row['ambiguity_reason']} |")
        lines.append("")
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"remaining_values={len(output)}")
    print(f"records={sum(int(row['count']) for row in output)}")
    for category in sorted(grouped, key=lambda value: order[value]):
        print(f"{category}: values={len(grouped[category])}; records={sum(int(row['count']) for row in grouped[category])}")


if __name__ == "__main__":
    main()
