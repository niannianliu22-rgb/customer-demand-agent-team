#!/usr/bin/env python3
"""Run RULE-013 school-dimension standardization as an audit-only artifact.

This utility deliberately does not rewrite unified_dataset.csv.  It evaluates
the current run artifact against the manually approved ACTIVE school dictionary
and writes only dimension-review evidence for a later controlled re-run of
Data Standardization.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml


RUN_ID = "RUN-202608-DEMAND-001"
ROOT = Path(__file__).resolve().parents[2]
RUN_ARTIFACTS = ROOT / "runs" / RUN_ID / "artifacts"
REVIEW_DIR = RUN_ARTIFACTS / "dimension_review"


def ordered(values: set[str]) -> list[str]:
    return sorted(values, key=lambda value: (value.casefold(), value))


def as_list(values: set[str]) -> list[str]:
    return sorted(values)


def main() -> None:
    aliases_path = ROOT / "config/data/school_aliases.yaml"
    rules_path = ROOT / "policies/business_rules.md"
    schema_path = ROOT / "schemas/canonical_schema.json"
    dataset_path = RUN_ARTIFACTS / "unified_dataset.csv"

    with aliases_path.open(encoding="utf-8") as handle:
        dictionary = yaml.safe_load(handle)
    with schema_path.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    rules_text = rules_path.read_text(encoding="utf-8")

    if dictionary.get("status") != "ACTIVE" or dictionary.get("business_rules_version") != "3.0":
        raise ValueError("school_aliases.yaml must be ACTIVE and aligned to Business Rules v3.0")
    if schema.get("business_rules_version") != "3.0" or "school_original" not in {
        field["name"] for field in schema["fields"]
    }:
        raise ValueError("canonical schema must define RULE-013 school fields under Business Rules v3.0")
    if "**Business Rules Version: 3.0**" not in rules_text or "RULE-013" not in rules_text:
        raise ValueError("Business Rules v3.0 with RULE-013 is required")

    alias_map: dict[str, dict] = {}
    canonical = {}
    for entity in dictionary["canonical_entities"]:
        if entity.get("status") != "ACTIVE":
            continue
        canonical[entity["canonical_name"]] = entity
        for alias in entity["aliases"]:
            if alias in alias_map:
                raise ValueError(f"duplicate active school alias: {alias}")
            alias_map[alias] = entity
    non_school = {
        value["original_value"]: value["classification"]
        for value in dictionary.get("non_school_values", [])
        if value.get("status") == "ACTIVE"
    }

    with dataset_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    canonical_stats = {
        name: {
            "canonical_name": name,
            "original_aliases": Counter(),
            "total_count": 0,
            "source_ids": set(),
            "years": set(),
            "departments": set(),
        }
        for name in canonical
    }
    unstandardized: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "source_ids": set(), "years": set(), "departments": set(), "country_values": set()}
    )
    conflicts: list[dict[str, str]] = []
    non_empty = canonical_rows = unknown_rows = non_school_rows = unstandardized_rows = 0

    for row in rows:
        # The present v1.0 artifact has only `school`; it is the source value
        # that becomes school_original in the future v1.1 controlled rewrite.
        original = (row.get("school") or "").strip()
        if not original:
            continue
        non_empty += 1
        country_original = (row.get("country") or "").strip()

        entity = alias_map.get(original)
        if entity:
            canonical_rows += 1
            stat = canonical_stats[entity["canonical_name"]]
            stat["total_count"] += 1
            stat["original_aliases"][original] += 1
            stat["source_ids"].add(row["source_id"])
            stat["years"].add(str(row["year"]))
            stat["departments"].add(row["department"])
            if country_original and country_original != entity["canonical_country"]:
                conflicts.append(
                    {
                        "source_id": row["source_id"],
                        "source_file": row["source_file"],
                        "source_sheet": row["source_sheet"],
                        "source_row_id": row["source_row_id"],
                        "year": row["year"],
                        "department": row["department"],
                        "school_original": original,
                        "school": entity["canonical_name"],
                        "country_original": country_original,
                        "canonical_country": entity["canonical_country"],
                        "conflict_type": "COUNTRY_SCHOOL_CONFLICT",
                    }
                )
        elif original in non_school:
            if non_school[original] == "UNKNOWN":
                unknown_rows += 1
            else:
                non_school_rows += 1
        else:
            unstandardized_rows += 1
            record = unstandardized[original]
            record["count"] += 1
            record["source_ids"].add(row["source_id"])
            record["years"].add(str(row["year"]))
            record["departments"].add(row["department"])
            if country_original:
                record["country_values"].add(country_original)

    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    unstandardized_path = REVIEW_DIR / "school_unstandardized_values.csv"
    with unstandardized_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["original_value", "count", "source_ids", "years", "departments", "country_values"],
        )
        writer.writeheader()
        for value, record in sorted(unstandardized.items(), key=lambda pair: (-pair[1]["count"], pair[0])):
            writer.writerow(
                {
                    "original_value": value,
                    "count": record["count"],
                    "source_ids": "|".join(as_list(record["source_ids"])),
                    "years": "|".join(as_list(record["years"])),
                    "departments": "|".join(as_list(record["departments"])),
                    "country_values": "|".join(ordered(record["country_values"])),
                }
            )

    conflict_path = REVIEW_DIR / "country_school_conflicts.csv"
    with conflict_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(conflicts[0]) if conflicts else [
            "source_id", "source_file", "source_sheet", "source_row_id", "year", "department",
            "school_original", "school", "country_original", "canonical_country", "conflict_type",
        ])
        writer.writeheader()
        writer.writerows(conflicts)

    observed_canonical = []
    for name, record in canonical_stats.items():
        if record["total_count"]:
            observed_canonical.append(
                {
                    "canonical_name": name,
                    "original_aliases": [
                        {"original_value": alias, "count": count}
                        for alias, count in sorted(record["original_aliases"].items())
                    ],
                    "total_count": record["total_count"],
                    "source_ids": as_list(record["source_ids"]),
                    "years": as_list(record["years"]),
                    "departments": as_list(record["departments"]),
                }
            )
    observed_canonical.sort(key=lambda item: (-item["total_count"], item["canonical_name"]))
    classified = canonical_rows + unknown_rows + non_school_rows
    result = {
        "run_id": RUN_ID,
        "artifact_type": "school_dimension_standardization_audit",
        "status": "COMPLETED",
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "business_rules_version": "3.0",
        "rule_id": "RULE-013",
        "canonical_schema_version": schema["schema_version"],
        "input_artifact": "runs/RUN-202608-DEMAND-001/artifacts/unified_dataset.csv",
        "input_artifact_modified": False,
        "school_original_interpretation": "Current unified_dataset.school is the original historical value; it is not rewritten by this audit.",
        "total_business_rows": len(rows),
        "non_empty_school_rows": non_empty,
        "canonical_standardized_rows": canonical_rows,
        "standardized_rows": classified,
        "unknown_rows": unknown_rows,
        "non_school_rows": non_school_rows,
        "unstandardized_rows": unstandardized_rows,
        "unstandardized_unique_values": len(unstandardized),
        "standardization_coverage": round(classified / non_empty, 6) if non_empty else 0,
        "canonical_school_count": len(observed_canonical),
        "canonical_school_rows": canonical_rows,
        "country_school_conflict_rows": len(conflicts),
        "country_school_conflict_types": len({(item["school"], item["country_original"], item["canonical_country"]) for item in conflicts}),
        "ranking_exclusions": {"NON_SCHOOL": non_school_rows, "UNKNOWN": unknown_rows},
        "canonical_schools": observed_canonical,
        "evidence_refs": {
            "school_aliases": "config/data/school_aliases.yaml",
            "business_rules": "policies/business_rules.md#rule-013",
            "canonical_schema": "schemas/canonical_schema.json",
            "unstandardized_values": "runs/RUN-202608-DEMAND-001/artifacts/dimension_review/school_unstandardized_values.csv",
            "country_conflicts": "runs/RUN-202608-DEMAND-001/artifacts/dimension_review/country_school_conflicts.csv",
        },
    }
    with (REVIEW_DIR / "school_standardization_result.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
