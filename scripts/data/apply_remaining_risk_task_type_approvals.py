#!/usr/bin/env python3
"""Apply the nine approved non-proofreading risk task-type decisions only."""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TASK_DIR = ROOT / "config" / "dimensions" / "task_type"
REVIEW = ROOT / "runs" / "RUN-202608-DEMAND-001" / "artifacts" / "dimension_review" / "task_type_manual_final_review_v2.csv"
RULE_FILE = TASK_DIR / "risk_high_confirmed_aliases.yaml"
EXPECTED = {
    "毕业论文": "Dissertation",
    "毕业论文全包": "Dissertation",
    "毕业论文半包": "Dissertation",
    "Matlab代码作业": "code/experiment",
    "神经系统代码": "code/experiment",
    "编程代码": "code/experiment",
    "assignment": "assignment",
    "project": "project",
    "考试": "考试",
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def stage_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> Path:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="", dir=path.parent, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
        return Path(handle.name)


def stage_text(path: Path, text: str) -> Path:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        return Path(handle.name)


def quote(value: str) -> str:
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def main() -> None:
    fields, rows = read_csv(REVIEW)
    targets = [row for row in rows if row["original_value"] in EXPECTED]
    if len(targets) != 9:
        raise ValueError(f"Expected 9 target rows, found {len(targets)}")
    for row in targets:
        expected = EXPECTED[row["original_value"]]
        if row["suggested_official_task_type"] != expected:
            raise ValueError(f"Unexpected suggested type for {row['original_value']}")
        if row["business_decision"]:
            raise ValueError(f"Already decided: {row['original_value']}")
        row["business_decision"] = "APPROVED"
        row["final_official_task_type"] = expected
        row["review_note"] = "manual_business_confirmation"

    lines = [
        "# ACTIVE risk high-confidence task_type aliases confirmed by business.",
        "aliases_version: \"1.0\"",
        "business_rules_version: \"10.0\"",
        "rule_id: RULE-020",
        "source: manual_business_confirmation",
        "status: ACTIVE",
        "entries:",
    ]
    for raw, canonical in EXPECTED.items():
        lines.extend([
            f"  - raw_value: {quote(raw)}",
            f"    canonical_task_type: {quote(canonical)}",
            "    source: manual_business_confirmation",
            "    status: ACTIVE",
        ])
    lines.append("")
    staged_review = stage_csv(REVIEW, fields, rows)
    staged_rule = stage_text(RULE_FILE, "\n".join(lines))
    os.replace(staged_review, REVIEW)
    os.replace(staged_rule, RULE_FILE)
    print("approved_risk_rows=9")


if __name__ == "__main__":
    main()
