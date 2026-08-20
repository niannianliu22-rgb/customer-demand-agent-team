"""Persist the user's approved school-alias decisions without changing data rows."""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
OVERRIDES = {
    "SCH-CAND-020": ("University of the Arts London", "英国"),
    "SCH-CAND-021": ("Queen Mary University of London", "英国"),
    "SCH-CAND-022": ("Australian National University", "澳洲"),
    "SCH-CAND-023": ("University College London", "英国"),
    "SCH-CAND-024": ("University of York", "英国"),
    "SCH-CAND-025": ("Newcastle University", "英国"),
}
NON_SCHOOL = {"SCH-NON-SCHOOL-001": "NON_SCHOOL", "SCH-NON-SCHOOL-002": "UNKNOWN"}
COUNTRY_CANONICAL = {"Australia": "澳洲", "United Kingdom": "英国", "Hong Kong": "香港", "United States": "美国", "New Zealand": "新西兰"}


def main(run_id: str):
    directory = ROOT / "runs" / run_id / "artifacts" / "dimension_review"
    review_path = directory / "school_alias_review.csv"
    candidates = json.loads((directory / "school_alias_candidates.json").read_text(encoding="utf-8"))
    with review_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader); fieldnames = reader.fieldnames
    candidate_map = {group["candidate_group_id"]: group for group in candidates["groups"]}
    entities = defaultdict(lambda: {"canonical_country": None, "aliases": []})
    for row in rows:
        group_id = row["candidate_group_id"]
        if group_id in NON_SCHOOL:
            decision = NON_SCHOOL[group_id]
            row.update(human_decision=decision, human_canonical_name=decision, human_notes="manual_business_confirmation")
            continue
        group = candidate_map[group_id]
        canonical, country = OVERRIDES.get(group_id, (group["suggested_canonical_name"], group["suggested_country"]))
        country = COUNTRY_CANONICAL.get(country, country)
        row.update(human_decision="APPROVED", human_canonical_name=canonical, human_notes="manual_business_confirmation")
        entities[canonical]["canonical_country"] = country
        entities[canonical]["aliases"].append(row["original_value"])
    with review_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames); writer.writeheader(); writer.writerows(rows)
    alias_doc = {
        "dictionary_name": "school_aliases",
        "dictionary_version": "1.0",
        "source": "manual_business_confirmation",
        "status": "ACTIVE",
        "business_rules_version": "3.0",
        "canonical_entities": [
            {"canonical_name": name, "canonical_country": entity["canonical_country"], "aliases": sorted(entity["aliases"]), "source": "manual_business_confirmation", "status": "ACTIVE"}
            for name, entity in sorted(entities.items())
        ],
        "non_school_values": [
            {"original_value": "/", "classification": "NON_SCHOOL", "exclude_from_school_ranking": True, "source": "manual_business_confirmation", "status": "ACTIVE"},
            {"original_value": "未知", "classification": "UNKNOWN", "exclude_from_school_ranking": True, "source": "manual_business_confirmation", "status": "ACTIVE"}
        ],
        "invariants": {"school_original_retained": True, "country_overwrite_allowed": False, "country_conflict_marker": "COUNTRY_SCHOOL_CONFLICT"}
    }
    path = ROOT / "config" / "data" / "school_aliases.yaml"
    path.write_text(yaml.safe_dump(alias_doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(json.dumps({"approved_school_entities": len(entities), "approved_aliases": sum(len(x["aliases"]) for x in entities.values()), "review_rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "RUN-202608-DEMAND-001")
