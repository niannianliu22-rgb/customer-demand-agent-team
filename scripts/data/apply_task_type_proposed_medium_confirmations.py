#!/usr/bin/env python3
"""Apply the approved PROPOSED_MEDIUM decisions without touching datasets."""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TASK_DIR = ROOT / "config" / "dimensions" / "task_type"
CANONICAL = TASK_DIR / "canonical.csv"
ACTIVE_ALIASES = TASK_DIR / "active_aliases.yaml"
REVIEW = ROOT / "runs" / "RUN-202608-DEMAND-001" / "artifacts" / "dimension_review" / "task_type_manual_final_review_v2.csv"

OVERRIDES = {
    "大论文辅导": "毕业论文辅导",
    "作业": "作业",
    "期末作业": "作业",
    "小组作业": "小组作业",
}
ADDITIONS = [
    ("毕业论文辅导", "MANUAL-TASK-TYPE-007"),
    ("作业", "MANUAL-TASK-TYPE-008"),
    ("小组作业", "MANUAL-TASK-TYPE-009"),
]


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


def yaml_quote(value: str) -> str:
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def stage_text(path: Path, text: str) -> Path:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        return Path(handle.name)


def main() -> None:
    canonical_fields, canonical_rows = read_csv(CANONICAL)
    present = {row["official_order_type"]: row for row in canonical_rows}
    for name, identifier in ADDITIONS:
        if name in present:
            if present[name]["official_task_type_id"] != identifier:
                raise ValueError(f"Unexpected existing canonical row for {name}")
            continue
        canonical_rows.append({
            "official_task_type_id": identifier,
            "official_task_type_id_source": "manual_business_confirmation",
            "official_order_type": name,
            "official_source_record_id": "RULE-018",
            "official_numeric_value": "",
        })
    canonical_names = {row["official_order_type"] for row in canonical_rows}

    review_fields, review_rows = read_csv(REVIEW)
    medium_rows = [row for row in review_rows if row["current_status"] == "PROPOSED_MEDIUM"]
    if len(medium_rows) != 41:
        raise ValueError(f"Expected 41 PROPOSED_MEDIUM rows, got {len(medium_rows)}")
    aliases: list[tuple[str, str]] = []
    for row in medium_rows:
        final = OVERRIDES.get(row["original_value"], row["suggested_official_task_type"])
        if final not in canonical_names:
            raise ValueError(f"Final type is not official: {row['original_value']} -> {final}")
        row["business_decision"] = "APPROVED"
        row["final_official_task_type"] = final
        row["review_note"] = "manual_business_confirmation"
        aliases.append((row["original_value"], final))
    if len(set(raw for raw, _ in aliases)) != 41:
        raise ValueError("Duplicate PROPOSED_MEDIUM aliases")

    yaml_lines = [
        "# ACTIVE task_type aliases confirmed in the PROPOSED_MEDIUM final review.",
        "aliases_version: \"1.0\"",
        "business_rules_version: \"8.0\"",
        "source: manual_business_confirmation",
        "status: ACTIVE",
        "dictionary_scope: RUN-202608-DEMAND-001 PROPOSED_MEDIUM approved values only",
        "entries:",
    ]
    for raw, final in aliases:
        yaml_lines.extend([
            f"  - raw_value: {yaml_quote(raw)}",
            f"    canonical_task_type: {yaml_quote(final)}",
            "    rule_id: RULE-018",
            "    source: manual_business_confirmation",
            "    status: ACTIVE",
        ])
    yaml_lines.append("")

    staged_canonical = stage_csv(CANONICAL, canonical_fields, canonical_rows)
    staged_review = stage_csv(REVIEW, review_fields, review_rows)
    staged_aliases = stage_text(ACTIVE_ALIASES, "\n".join(yaml_lines))
    os.replace(staged_canonical, CANONICAL)
    os.replace(staged_review, REVIEW)
    os.replace(staged_aliases, ACTIVE_ALIASES)
    print(f"official_task_type_count={len(canonical_rows)}")
    print("approved_proposed_medium=41")
    print(f"active_aliases={len(aliases)}")


if __name__ == "__main__":
    main()
