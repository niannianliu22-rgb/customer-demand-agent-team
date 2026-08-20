#!/usr/bin/env python3
"""Complete V1 by applying the eight safe-passed NON_SCHOOL classifications.

This recovery step is deliberately narrow: it uses the already-created V1
backups as immutable evidence and changes only values previously classified as
safe NON_SCHOOL candidates.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "RUN-202608-DEMAND-001"
ARTIFACTS = ROOT / "runs" / RUN_ID / "artifacts"
DIMENSION = ARTIFACTS / "dimension_review"
BACKUPS = ARTIFACTS / "backups"
CONFIG = ROOT / "config/data/school_aliases.yaml"
DATASET = ARTIFACTS / "unified_dataset.csv"
SCHEMA = ROOT / "schemas/canonical_schema.json"
SAFE_NON_SCHOOL_SOURCE = DIMENSION / "school_unstandardized_review_round2.csv"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def active_alias_map(dictionary: dict) -> dict[str, dict]:
    return {alias: entity for entity in dictionary["canonical_entities"] if entity.get("status") == "ACTIVE" for alias in entity["aliases"]}


def joined(values: set[str]) -> str:
    return "|".join(sorted(values))


def main() -> None:
    backup_csv = BACKUPS / "unified_dataset_pre_school_standardization_v1.csv"
    backup_xlsx = BACKUPS / "unified_dataset_pre_school_standardization_v1.xlsx"
    backup_dictionary = BACKUPS / "school_aliases_pre_school_standardization_v1.yaml"
    if not all(path.exists() for path in (backup_csv, backup_xlsx, backup_dictionary)):
        raise FileNotFoundError("V1 pre-writeback backups are required")
    with CONFIG.open(encoding="utf-8") as handle:
        dictionary = yaml.safe_load(handle)
    with backup_dictionary.open(encoding="utf-8") as handle:
        before_dictionary = yaml.safe_load(handle)
    with SAFE_NON_SCHOOL_SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        non_school_rows = [row for row in csv.DictReader(handle) if row["confidence"] == "NON_SCHOOL"]
    if len(non_school_rows) != 8:
        raise ValueError("expected eight safe-passed NON_SCHOOL values")
    existing = {item["original_value"] for item in dictionary["non_school_values"]}
    additions = []
    for row in non_school_rows:
        value = row["original_value"]
        if value not in existing:
            dictionary["non_school_values"].append({
                "original_value": value,
                "classification": "NON_SCHOOL",
                "exclude_from_school_ranking": True,
                "source": "safe_passed_round2",
                "status": "ACTIVE",
            })
            additions.append(value)
    dictionary["non_school_values"].sort(key=lambda item: (item["original_value"].casefold(), item["original_value"]))
    dictionary["update_note"] += " Eight safe-passed Round-2 NON_SCHOOL values classified in the same V1 writeback."
    with CONFIG.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(dictionary, handle, allow_unicode=True, sort_keys=False)

    with DATASET.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    non_school = {item["original_value"]: item["classification"] for item in dictionary["non_school_values"] if item["status"] == "ACTIVE"}
    for row in rows:
        raw = row["school_original"]
        if raw in non_school:
            row["school"] = non_school[raw]
            row["country_school_conflict"] = ""
    with DATASET.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    # The XLSX is regenerated from the corrected CSV while preserving only canonical fields.
    from openpyxl import Workbook
    workbook = Workbook(write_only=True); sheet = workbook.create_sheet("unified_dataset")
    sheet.append(fields)
    for row in rows: sheet.append([row[field] for field in fields])
    workbook.save(ARTIFACTS / "unified_dataset.xlsx")

    before_aliases = active_alias_map(before_dictionary)
    after_aliases = active_alias_map(dictionary)
    before_counts = Counter(); after_counts = Counter(); classification_counts = Counter(); mapping = defaultdict(lambda: {"count": 0, "source_ids": set(), "years": set(), "departments": set()})
    conflicts = 0
    for row in rows:
        raw = row["school_original"]
        if raw in before_aliases: before_counts[before_aliases[raw]["canonical_name"]] += 1
        if raw in after_aliases: after_counts[after_aliases[raw]["canonical_name"]] += 1
        classification = "CANONICAL_SCHOOL" if raw in after_aliases else (row["school"] or "EMPTY")
        classification_counts[classification] += 1
        conflicts += row["country_school_conflict"] == "COUNTRY_SCHOOL_CONFLICT"
        entry = mapping[raw if raw else "<EMPTY>"]
        entry["count"] += 1; entry["source_ids"].add(row["source_id"]); entry["years"].add(row["year"]); entry["departments"].add(row["department"])
        entry.update({"final_school": row["school"], "classification": classification, "canonical_country": after_aliases.get(raw, {}).get("canonical_country", "")})
    mapping_path = DIMENSION / "school_standardization_final_mapping.csv"
    mapping_fields = ["school_original","final_school","classification","mapping_basis","canonical_country","record_count","source_ids","years","departments"]
    with mapping_path.open("w", encoding="utf-8", newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=mapping_fields); writer.writeheader()
        for raw, item in sorted(mapping.items(), key=lambda pair:(-pair[1]["count"],pair[0])):
            basis = "existing_active_dictionary" if raw in before_aliases else (dictionary.get("alias_provenance",{}).get(raw,""))
            if item["classification"] == "NON_SCHOOL": basis = "safe_passed_round2" if raw in additions else "existing_non_school_values"
            elif item["classification"] == "UNRESOLVED": basis = "manual_business_confirmation_round3"
            elif item["classification"] == "NON_UNIVERSITY_ENTITY": basis = "manual_business_confirmation_round3"
            elif item["classification"] == "UNSTANDARDIZED": basis = "pending_human_review"
            elif item["classification"] == "UNKNOWN": basis = "existing_non_school_values"
            elif item["classification"] == "EMPTY": basis = "empty_school_value"
            writer.writerow({"school_original":raw,"final_school":item["final_school"],"classification":item["classification"],"mapping_basis":basis,"canonical_country":item["canonical_country"],"record_count":item["count"],"source_ids":joined(item["source_ids"]),"years":joined(item["years"]),"departments":joined(item["departments"])})
    canonical_rows = "\n".join(f"| {name} | {before_counts[name]} | {after_counts[name]} | {after_counts[name]-before_counts[name]:+d} |" for name in sorted(set(before_counts)|set(after_counts)))
    report = f"""# School Standardization V1 — Final Diff Report

Generated at: {datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')}  
Run: `{RUN_ID}`

## Backup evidence

| Artifact | Backup | SHA-256 before writeback |
|---|---|---|
| unified_dataset.csv | `{backup_csv.relative_to(ROOT)}` | `{digest(backup_csv)}` |
| unified_dataset.xlsx | `{backup_xlsx.relative_to(ROOT)}` | `{digest(backup_xlsx)}` |
| school_aliases.yaml | `{backup_dictionary.relative_to(ROOT)}` | `{digest(backup_dictionary)}` |

## Record-level outcome

| Metric | Count |
|---|---:|
| Original records | 818 |
| Output records | {len(rows)} |
| Canonical-school standardized records | {classification_counts['CANONICAL_SCHOOL']} |
| `UNRESOLVED` records | {classification_counts['UNRESOLVED']} |
| `NON_UNIVERSITY_ENTITY` records | {classification_counts['NON_UNIVERSITY_ENTITY']} |
| `UNSTANDARDIZED` pending-review records | {classification_counts['UNSTANDARDIZED']} |
| `NON_SCHOOL` records | {classification_counts['NON_SCHOOL']} |
| `UNKNOWN` records | {classification_counts['UNKNOWN']} |
| Empty school values | {classification_counts['EMPTY']} |
| `COUNTRY_SCHOOL_CONFLICT` markers | {conflicts} |
| Row-count anomaly | {'NO — 818 input records = 818 output records' if len(rows)==818 else 'YES'} |

## Dictionary update

- Dictionary version: `1.0` → `1.1`
- Newly added ACTIVE canonical alias mappings: 70 (67 safe-passed Round-2 aliases + 3 manual Round-3 approvals).
- Safe-passed non-school classifications added: {len(additions)}.
- Canonical university entities: {len(before_dictionary['canonical_entities'])} → {len(dictionary['canonical_entities'])}.
- `NON_UNIVERSITY_ENTITY` and `UNRESOLVED` entries are not canonical university entities.

## Canonical school record counts: before → after

| Canonical school | Before | After | Delta |
|---|---:|---:|---:|
{canonical_rows}

See `school_standardization_final_mapping.csv` for every raw school value and its final school classification. `school_original` is preserved in the updated dataset. No original record was deleted.
"""
    (DIMENSION / "school_standardization_final_diff_report.md").write_text(report,encoding="utf-8")
    shutil.copy2(CONFIG, DIMENSION / "school_aliases_v1.1.yaml")
    assert len(rows) == 818 and classification_counts['UNRESOLVED'] == 9 and classification_counts['NON_UNIVERSITY_ENTITY'] == 2 and classification_counts['UNSTANDARDIZED'] == 74


if __name__ == "__main__": main()
