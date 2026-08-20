#!/usr/bin/env python3
"""Build a read-only human-review queue for Single Task PROPOSED_MEDIUM rows."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DIMENSION = ROOT / "runs" / "RUN-202608-DEMAND-001" / "artifacts" / "dimension_review"
BUSINESS_REVIEW = DIMENSION / "task_type_business_final_review.csv"
ALIASES = ROOT / "config" / "dimensions" / "task_type" / "aliases_candidate.csv"
OUTPUT_CSV = DIMENSION / "task_type_proposed_medium_review.csv"
OUTPUT_MD = DIMENSION / "task_type_proposed_medium_review_summary.md"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def main() -> None:
    _, business_rows = read_csv(BUSINESS_REVIEW)
    _, alias_rows = read_csv(ALIASES)
    aliases = {row["raw_value"]: row for row in alias_rows}
    candidates = [
        row
        for row in business_rows
        if row["current_classification"] == "PROPOSED_MEDIUM"
        and row.get("task_type_mode", "") != "MULTI_TASK"
    ]
    if len(candidates) != 41:
        raise ValueError(f"Expected 41 PROPOSED_MEDIUM single-task rows, got {len(candidates)}")

    output_rows: list[dict[str, str]] = []
    for row in candidates:
        alias = aliases.get(row["raw_value"])
        if not alias:
            raise ValueError(f"No source context found for {row['raw_value']!r}")
        output_rows.append(
            {
                "original_value": row["raw_value"],
                "count": row["record_count"],
                "suggested_official_task_type": row["proposed_official_task_type"],
                "confidence": alias["confidence"],
                "mapping_reason": alias["evidence"],
                "source_ids": alias["source_ids"],
                "years": alias["years"],
                "departments": alias["departments"],
                "sample_context": row["sample_context"],
                "decision": "",
                "final_official_task_type": "",
                "review_note": "",
            }
        )
    output_rows.sort(
        key=lambda r: (r["suggested_official_task_type"], -int(r["count"]), r["original_value"])
    )
    fields = list(output_rows[0])
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(output_rows)

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in output_rows:
        groups[row["suggested_official_task_type"]].append(row)
    lines = [
        "# Single Task PROPOSED_MEDIUM 人工审核汇总",
        "",
        "本文件仅提供人工审核证据；`decision`、`final_official_task_type`、`review_note` 均未写入。",
        "",
        f"- 原始值数量：{len(output_rows)}",
        f"- 涉及记录数：{sum(int(row['count']) for row in output_rows)}",
        f"- 建议 official task type 数量：{len(groups)}",
        "",
    ]
    for official in sorted(groups):
        rows = groups[official]
        lines.extend(
            [
                f"## 建议：{official}（{len(rows)} 个原始值 / {sum(int(row['count']) for row in rows)} 条记录）",
                "",
                "| 原始值 | 数量 | 建议类型 | 置信度 | 原因 | 来源 |",
                "|---|---:|---|---|---|---|",
            ]
        )
        for row in rows:
            reason = row["mapping_reason"].replace("|", "\\|")
            lines.append(
                f"| {row['original_value']} | {row['count']} | {official} | {row['confidence']} | {reason} | {row['source_ids']} |"
            )
        lines.append("")
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"candidate_values={len(output_rows)}")
    print(f"records={sum(int(row['count']) for row in output_rows)}")
    print(f"official_type_groups={len(groups)}")
    for official in sorted(groups):
        print(f"{official}: {len(groups[official])}")


if __name__ == "__main__":
    main()
