#!/usr/bin/env python3
"""Apply approved V1 school mappings with backups and audit artifacts.

Scope is school fields only.  Dates, amounts, and all other current dataset
values are copied unchanged.
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
from openpyxl import Workbook


ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "RUN-202608-DEMAND-001"
ARTIFACTS = ROOT / "runs" / RUN_ID / "artifacts"
DIMENSION = ARTIFACTS / "dimension_review"
CONFIG = ROOT / "config/data/school_aliases.yaml"
SCHEMA = ROOT / "schemas/canonical_schema.json"
INPUT_CSV = ARTIFACTS / "unified_dataset.csv"
INPUT_XLSX = ARTIFACTS / "unified_dataset.xlsx"
BACKUP_DIR = ARTIFACTS / "backups"

MANUAL_APPROVALS = {
    "cmu": ("Carnegie Mellon University", "美国"),
    "psu": ("Pennsylvania State University", "美国"),
    "伯克利": ("University of California, Berkeley", "美国"),
}
UNRESOLVED = {"波士顿", "维多利亚", "UCD", "加州大学", "北卡", "华盛顿"}
NON_UNIVERSITY = {
    "多伦多高中": "HIGH_SCHOOL",
    "麦唐纳国际学校": "INTERNATIONAL_SCHOOL",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def list_join(values: set[str]) -> str:
    return "|".join(sorted(values))


def build_alias_map(dictionary: dict) -> dict[str, dict]:
    aliases = {}
    for entity in dictionary["canonical_entities"]:
        if entity.get("status") != "ACTIVE":
            continue
        for alias in entity["aliases"]:
            if alias in aliases and aliases[alias]["canonical_name"] != entity["canonical_name"]:
                raise ValueError(f"ambiguous ACTIVE alias: {alias}")
            aliases[alias] = entity
    return aliases


def main() -> None:
    with CONFIG.open(encoding="utf-8") as handle:
        before_dictionary = yaml.safe_load(handle)
    before_canonical_count = len(before_dictionary["canonical_entities"])
    if before_dictionary.get("status") != "ACTIVE" or before_dictionary.get("business_rules_version") != "3.0":
        raise ValueError("expected ACTIVE school dictionary governed by Business Rules v3.0")
    with SCHEMA.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    fields = [field["name"] for field in schema["fields"]]
    required = {"school_original", "school", "country_original", "country_school_conflict"}
    if not required <= set(fields):
        raise ValueError("canonical schema does not contain the required school V1 fields")
    with INPUT_CSV.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))

    high_path = DIMENSION / "school_unstandardized_review_round2.csv"
    with high_path.open(encoding="utf-8-sig", newline="") as handle:
        high_rows = [row for row in csv.DictReader(handle) if row["confidence"] == "PROPOSED_HIGH"]
    if len(high_rows) != 67:
        raise ValueError("expected 67 safe-passed PROPOSED_HIGH aliases")

    # Back up all artifacts that will be overwritten before any mutation.
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backups = {
        "unified_csv": BACKUP_DIR / "unified_dataset_pre_school_standardization_v1.csv",
        "unified_xlsx": BACKUP_DIR / "unified_dataset_pre_school_standardization_v1.xlsx",
        "dictionary": BACKUP_DIR / "school_aliases_pre_school_standardization_v1.yaml",
    }
    for source, destination in [(INPUT_CSV, backups["unified_csv"]), (INPUT_XLSX, backups["unified_xlsx"]), (CONFIG, backups["dictionary"])]:
        if destination.exists():
            raise FileExistsError(f"backup already exists; refusing to overwrite: {destination}")
        shutil.copy2(source, destination)

    before_aliases = build_alias_map(before_dictionary)
    dictionary = before_dictionary
    entities = {entity["canonical_name"]: entity for entity in dictionary["canonical_entities"]}
    alias_provenance = dictionary.setdefault("alias_provenance", {})
    additions = []

    def add_alias(alias: str, canonical_name: str, country: str, source: str) -> None:
        existing = before_aliases.get(alias)
        if existing:
            if existing["canonical_name"] != canonical_name:
                raise ValueError(f"existing alias points elsewhere: {alias}")
            return
        entity = entities.get(canonical_name)
        if entity is None:
            entity = {
                "canonical_name": canonical_name,
                "canonical_country": country,
                "aliases": [],
                "source": source,
                "status": "ACTIVE",
            }
            dictionary["canonical_entities"].append(entity)
            entities[canonical_name] = entity
        elif entity["canonical_country"] != country:
            raise ValueError(f"canonical country conflict for {canonical_name}")
        if alias not in entity["aliases"]:
            entity["aliases"].append(alias)
            additions.append({"alias": alias, "canonical_name": canonical_name, "canonical_country": country, "source": source})
        alias_provenance[alias] = source

    for row in high_rows:
        add_alias(row["original_value"], row["suggested_canonical_name"], row["suggested_canonical_country"], "safe_passed_round2")
    for alias, (canonical_name, country) in MANUAL_APPROVALS.items():
        add_alias(alias, canonical_name, country, "manual_business_confirmation_round3")

    dictionary["dictionary_version"] = "1.1"
    dictionary["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    dictionary["update_note"] = "V1 school writeback: 67 safe-passed Round-2 aliases and 3 manual Round-3 approvals added."
    dictionary["non_university_entities"] = [
        {
            "original_value": value,
            "entity_type": entity_type,
            "classification": "NON_UNIVERSITY_ENTITY",
            "exclude_from_university_ranking": True,
            "source": "manual_business_confirmation_round3",
            "status": "ACTIVE",
        }
        for value, entity_type in NON_UNIVERSITY.items()
    ]
    dictionary["unresolved_values"] = [
        {
            "original_value": value,
            "classification": "UNRESOLVED",
            "exclude_from_university_ranking": True,
            "source": "manual_business_confirmation_round3",
            "status": "ACTIVE",
        }
        for value in sorted(UNRESOLVED)
    ]
    dictionary["canonical_entities"].sort(key=lambda entity: entity["canonical_name"])
    for entity in dictionary["canonical_entities"]:
        entity["aliases"] = sorted(entity["aliases"], key=lambda value: (value.casefold(), value))
    with CONFIG.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(dictionary, handle, allow_unicode=True, sort_keys=False)

    after_aliases = build_alias_map(dictionary)
    non_school = {item["original_value"]: item["classification"] for item in dictionary.get("non_school_values", []) if item.get("status") == "ACTIVE"}
    non_university = {item["original_value"]: item for item in dictionary["non_university_entities"] if item["status"] == "ACTIVE"}
    unresolved = {item["original_value"] for item in dictionary["unresolved_values"] if item["status"] == "ACTIVE"}
    before_counts = Counter()
    after_counts = Counter()
    mapping_stats = defaultdict(lambda: {"count": 0, "source_ids": set(), "years": set(), "departments": set(), "mapping_basis": set(), "canonical_country": ""})
    output_rows = []
    classification_counts = Counter()
    country_conflicts = 0

    for source in source_rows:
        raw_school = (source.get("school") or "").strip()
        country_original = (source.get("country") or "").strip()
        before_entity = before_aliases.get(raw_school)
        if before_entity:
            before_counts[before_entity["canonical_name"]] += 1
        final_school = ""
        classification = "EMPTY"
        basis = "empty_school_value"
        canonical_country = ""
        entity = after_aliases.get(raw_school)
        if entity:
            final_school = entity["canonical_name"]
            classification = "CANONICAL_SCHOOL"
            basis = alias_provenance.get(raw_school, "existing_active_dictionary")
            canonical_country = entity["canonical_country"]
            after_counts[final_school] += 1
        elif raw_school in non_school:
            final_school = non_school[raw_school]
            classification = non_school[raw_school]
            basis = "existing_non_school_values"
        elif raw_school in non_university:
            final_school = "NON_UNIVERSITY_ENTITY"
            classification = "NON_UNIVERSITY_ENTITY"
            basis = "manual_business_confirmation_round3"
        elif raw_school in unresolved:
            final_school = "UNRESOLVED"
            classification = "UNRESOLVED"
            basis = "manual_business_confirmation_round3"
        elif raw_school:
            final_school = "UNSTANDARDIZED"
            classification = "UNSTANDARDIZED"
            basis = "pending_human_review"
        conflict = ""
        if canonical_country and country_original and country_original != canonical_country:
            conflict = "COUNTRY_SCHOOL_CONFLICT"
            country_conflicts += 1
        row = {field: source.get(field, "") for field in fields}
        row["country_original"] = country_original
        row["country"] = source.get("country", "")
        row["school_original"] = raw_school
        row["school"] = final_school
        row["country_school_conflict"] = conflict
        output_rows.append(row)
        stat = mapping_stats[raw_school if raw_school else "<EMPTY>"]
        stat["count"] += 1
        stat["source_ids"].add(source["source_id"])
        stat["years"].add(source["year"])
        stat["departments"].add(source["department"])
        stat["mapping_basis"].add(basis)
        stat["canonical_country"] = canonical_country
        stat["final_school"] = final_school
        stat["classification"] = classification
        classification_counts[classification] += 1
    if len(output_rows) != len(source_rows):
        raise ValueError("unexpected row count change")

    with INPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet("unified_dataset")
    worksheet.append(fields)
    for row in output_rows:
        worksheet.append([row[field] for field in fields])
    workbook.save(INPUT_XLSX)

    mapping_path = DIMENSION / "school_standardization_final_mapping.csv"
    mapping_fields = [
        "school_original", "final_school", "classification", "mapping_basis", "canonical_country", "record_count",
        "source_ids", "years", "departments",
    ]
    with mapping_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=mapping_fields)
        writer.writeheader()
        for raw, stat in sorted(mapping_stats.items(), key=lambda item: (-item[1]["count"], item[0])):
            writer.writerow({
                "school_original": raw,
                "final_school": stat["final_school"],
                "classification": stat["classification"],
                "mapping_basis": "|".join(sorted(stat["mapping_basis"])),
                "canonical_country": stat["canonical_country"],
                "record_count": stat["count"],
                "source_ids": list_join(stat["source_ids"]),
                "years": list_join(stat["years"]),
                "departments": list_join(stat["departments"]),
            })

    all_canonicals = sorted(set(before_counts) | set(after_counts))
    canonical_table = "\n".join(
        f"| {name} | {before_counts[name]} | {after_counts[name]} | {after_counts[name] - before_counts[name]:+d} |"
        for name in all_canonicals
    )
    report = f"""# School Standardization V1 — Final Diff Report

Generated at: {datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}  
Run: `{RUN_ID}`  
Scope: school-dimension writeback only. Date, amount, and all non-school source values were copied unchanged.

## Backup evidence

| Artifact | Backup | SHA-256 before writeback |
|---|---|---|
| unified_dataset.csv | `{backups['unified_csv'].relative_to(ROOT)}` | `{sha256(backups['unified_csv'])}` |
| unified_dataset.xlsx | `{backups['unified_xlsx'].relative_to(ROOT)}` | `{sha256(backups['unified_xlsx'])}` |
| school_aliases.yaml | `{backups['dictionary'].relative_to(ROOT)}` | `{sha256(backups['dictionary'])}` |

## Record-level outcome

| Metric | Count |
|---|---:|
| Original records | {len(source_rows)} |
| Output records | {len(output_rows)} |
| Canonical-school standardized records | {classification_counts['CANONICAL_SCHOOL']} |
| `UNRESOLVED` records | {classification_counts['UNRESOLVED']} |
| `NON_UNIVERSITY_ENTITY` records | {classification_counts['NON_UNIVERSITY_ENTITY']} |
| `UNSTANDARDIZED` pending-review records | {classification_counts['UNSTANDARDIZED']} |
| `NON_SCHOOL` records | {classification_counts['NON_SCHOOL']} |
| `UNKNOWN` records | {classification_counts['UNKNOWN']} |
| Empty school values | {classification_counts['EMPTY']} |
| `COUNTRY_SCHOOL_CONFLICT` markers | {country_conflicts} |
| Row-count anomaly | {'NO — 818 input records = 818 output records' if len(source_rows) == len(output_rows) == 818 else 'YES'} |

## Dictionary update

- Dictionary version: `1.0` → `1.1`
- Newly added ACTIVE alias mappings: {len(additions)} (67 safe-passed Round-2 aliases + 3 manual Round-3 approvals)
- Canonical university entities: {before_canonical_count} → {len(dictionary['canonical_entities'])}
- Non-university entities are stored only under `non_university_entities`, not `canonical_entities`.
- The six explicitly unresolved values are stored only under `unresolved_values`, not `canonical_entities`.

## Canonical school record counts: before → after

Before counts apply the pre-writeback ACTIVE dictionary; after counts apply dictionary v1.1.

| Canonical school | Before | After | Delta |
|---|---:|---:|---:|
{canonical_table}

## Mapping evidence

Complete raw-value → final-value detail: `runs/{RUN_ID}/artifacts/dimension_review/school_standardization_final_mapping.csv`.
Raw school values are retained in `school_original`; standardized output is in `school`. No original business record was deleted.
"""
    report_path = DIMENSION / "school_standardization_final_diff_report.md"
    report_path.write_text(report, encoding="utf-8")
    snapshot = DIMENSION / "school_aliases_v1.1.yaml"
    shutil.copy2(CONFIG, snapshot)

    # Finalization record becomes evidence of the three human approvals only.
    finalization_path = DIMENSION / "school_manual_finalization_round3.csv"
    with finalization_path.open(encoding="utf-8-sig", newline="") as handle:
        finalization_rows = list(csv.DictReader(handle))
        finalization_fields = list(finalization_rows[0])
    for row in finalization_rows:
        if row["raw_value"] in MANUAL_APPROVALS:
            row["final_decision"] = "APPROVED"
            row["final_canonical"] = MANUAL_APPROVALS[row["raw_value"]][0]
            row["review_note"] = "manual_business_confirmation; V1 dictionary writeback applied"
    with finalization_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=finalization_fields)
        writer.writeheader()
        writer.writerows(finalization_rows)


if __name__ == "__main__":
    main()
