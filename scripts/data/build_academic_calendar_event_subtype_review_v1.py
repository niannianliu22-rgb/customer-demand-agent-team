#!/usr/bin/env python3
"""Create a candidate-only Event Subtype Standardization V1 review package.

This script never changes the frozen v1.1 calendar.  Every proposed mapping is
explicitly marked REVIEW_REQUIRED for human confirmation.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_event_type_confirmation_v1/academic_calendar_standardized_v1_1.csv"
OUT = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_event_subtype_review"


def candidate(event_type: str, name: str):
    """Return candidate subtype, reason, relevance and issue from raw official wording."""
    s = name.casefold()
    # Ordered, exact manual approvals from Event Type Round 1 come first.
    exact = {
        "December Exam and Assessment Diet": ("EXAM_AND_ASSESSMENT", "Official wording is a combined examination and assessment diet.", "DIRECT", "Approved parent-type treatment; subtype retains both semantics."),
        "Revision and examination period": ("REVISION_AND_EXAM", "Official wording defines one continuous revision and examination period.", "DIRECT", "Approved parent-type treatment; do not split into two records."),
        "Semester 1 assessment and exams": ("ASSESSMENT_AND_EXAM", "Official wording explicitly combines assessment and examinations.", "DIRECT", "Approved parent-type treatment; subtype retains both semantics."),
        "Teaching and Assessment weeks - Term 1": ("TEACHING_AND_ASSESSMENT", "Official wording combines teaching and assessment weeks.", "DIRECT", "Approved parent-type treatment; do not simplify to pure assessment."),
        "Teaching and assessment weeks - Term 2": ("TEACHING_AND_ASSESSMENT", "Official wording combines teaching and assessment weeks.", "DIRECT", "Approved parent-type treatment; do not simplify to pure assessment."),
        "Teaching and assessment weeks - Term 3": ("TEACHING_AND_ASSESSMENT", "Official wording combines teaching and assessment weeks.", "DIRECT", "Approved parent-type treatment; do not simplify to pure assessment."),
    }
    if name in exact:
        return exact[name]
    if event_type == "EXAM":
        if "final assessment" in s:
            return ("FINAL_ASSESSMENT", "Official wording says final assessment rather than an examination.", "DIRECT", "Parent EXAM may need future confirmation; retain evidence without changing it in this review.")
        if "final" in s:
            return ("FINAL_EXAM", "Official wording explicitly identifies final examinations.", "DIRECT", "")
        return ("GENERAL_EXAM", "Official wording indicates an examination/exam period without a narrower confirmed semantic.", "DIRECT", "")
    if event_type == "RESIT":
        if "deferred" in s:
            return ("DEFERRED_EXAM", "Official wording identifies a deferred examination period.", "DIRECT", "Deferred and resit/supplementary treatment requires human confirmation before freezing.")
        if "supplementary" in s or "special/" in s:
            return ("SUPPLEMENTARY_EXAM", "Official wording identifies supplementary/special examinations.", "DIRECT", "")
        return ("RESIT_EXAM", "Official wording identifies a resit examination.", "DIRECT", "")
    if event_type == "TEACHING":
        if "resumes" in s or "main intake" in s:
            return ("TEACHING_START", "Official wording denotes a teaching resumption or intake start.", "CONTEXTUAL", "Some 'intake' labels may be programme-administration rather than a universal teaching start.")
        if "classes" in s and ("fall" in s or "summer" in s):
            return ("TEACHING_START", "Official wording denotes classes commencing for the named session.", "CONTEXTUAL", "Confirm whether date is a start event or an interval in the source calendar.")
        return ("TEACHING_PERIOD", "Official wording denotes a term, semester, block, or teaching weeks interval.", "CONTEXTUAL", "")
    if event_type == "ASSESSMENT":
        return ("ASSESSMENT_PERIOD", "Official wording denotes a standalone assessment period/weeks.", "DIRECT", "")
    if event_type == "REVISION":
        return ("REVISION_PERIOD", "Official wording denotes revision, study break, or pre-examination preparation.", "DIRECT", "")
    if event_type == "RESULTS":
        return ("RESULTS_RELEASE", "Official wording denotes publication/release of results.", "CONTEXTUAL", "")
    if event_type == "ORIENTATION":
        if "arrival" in s:
            return ("ARRIVAL", "Official wording denotes campus arrival rather than orientation instruction.", "CONTEXTUAL", "Arrival is adjacent to, but semantically narrower than, orientation.")
        if "induction" in s:
            return ("INDUCTION_WEEK", "Official wording explicitly identifies induction week.", "CONTEXTUAL", "")
        if "welcome" in s or "introduction" in s:
            return ("WELCOME_WEEK", "Official wording explicitly identifies welcome/introduction activity.", "CONTEXTUAL", "")
        if "international" in s:
            return ("INTERNATIONAL_ORIENTATION", "Official wording specifically scopes orientation to international students.", "CONTEXTUAL", "Scope may be cohort-specific.")
        return ("ORIENTATION_PERIOD", "Official wording denotes an orientation period/week.", "CONTEXTUAL", "")
    if event_type == "READING":
        if "field trip" in s:
            return ("READING_AND_FIELD_TRIP", "Official wording combines reading week and field trip activity.", "CONTEXTUAL", "Mixed academic activity; not a direct task-type signal on its own.")
        return ("READING_WEEK", "Official wording identifies a reading week.", "CONTEXTUAL", "")
    if event_type == "VACATION":
        if "christmas" in s:
            return ("CHRISTMAS_VACATION", "Official wording identifies the Christmas vacation.", "CONTEXTUAL", "")
        if "summer" in s:
            return ("SUMMER_VACATION", "Official wording identifies the summer vacation.", "CONTEXTUAL", "")
        if "winter" in s:
            return ("WINTER_VACATION", "Official wording identifies the winter vacation/break.", "CONTEXTUAL", "")
        return ("GENERAL_VACATION", "Official wording identifies a vacation period without a named season.", "CONTEXTUAL", "")
    if event_type == "BREAK":
        if "inter-semester" in s:
            return ("INTERSEMESTER_BREAK", "Official wording identifies a break between semesters.", "CONTEXTUAL", "")
        if "mid-semester" in s or "mid term" in s:
            return ("MID_SEMESTER_BREAK", "Official wording identifies a mid-semester/term break.", "CONTEXTUAL", "")
        if "teaching break" in s:
            return ("TEACHING_BREAK", "Official wording identifies a teaching break.", "CONTEXTUAL", "")
        if "study break" in s:
            return ("STUDY_BREAK", "Official wording identifies a non-teaching study break.", "CONTEXTUAL", "")
        if "fall break" in s:
            return ("FALL_BREAK", "Official wording identifies a fall break.", "CONTEXTUAL", "")
        if "thanksgiving" in s:
            return ("HOLIDAY_BREAK", "Official wording identifies a named holiday.", "CONTEXTUAL", "Holiday may not be an academic demand signal by itself.")
        if "main intake" in s:
            return ("POST_INTAKE_BREAK", "Official wording identifies a break after a named intake.", "CONTEXTUAL", "Programme-specific intake context may need confirmation.")
        return ("GENERAL_BREAK", "Official wording identifies a break without a narrower semantic.", "CONTEXTUAL", "")
    raise ValueError(f"Unexpected event type: {event_type}")


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with SOURCE.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    included = [r for r in rows if r["record_role"] == "ACADEMIC_EVENT"]
    excluded = [r for r in rows if r["record_role"] == "PERIOD_METADATA"]
    groups = defaultdict(list)
    for row in included:
        groups[(row["event_type"], row["event_name_original"])].append(row)

    details = []
    for (etype, raw), members in sorted(groups.items()):
        subtype, reason, relevance, issue = candidate(etype, raw)
        details.append({
            "event_type": etype, "event_name_original": raw, "current_event_subtype": " | ".join(sorted({x["event_subtype"] for x in members if x["event_subtype"]})) or "UNSPECIFIED",
            "candidate_event_subtype": subtype, "record_count": len(members),
            "schools": " | ".join(sorted({x["school"] for x in members})),
            "countries": " | ".join(sorted({x["country"] for x in members})),
            "semantic_reason": reason, "mapping_confidence": "MEDIUM", "demand_mapping_relevance": relevance,
            "potential_semantic_issue": issue or "NONE", "manual_decision": "REVIEW_REQUIRED", "manual_note": "",
        })
    detail_fields = list(details[0])
    write_csv(OUT / "event_subtype_raw_event_mapping.csv", detail_fields, details)

    summary_groups = defaultdict(list)
    for d in details:
        summary_groups[(d["event_type"], d["candidate_event_subtype"], d["demand_mapping_relevance"])].append(d)
    summaries = []
    for (etype, subtype, relevance), members in sorted(summary_groups.items()):
        summaries.append({
            "event_type": etype, "candidate_event_subtype": subtype,
            "raw_event_count": len(members), "record_count": sum(int(x["record_count"]) for x in members),
            "school_count": len(set().union(*[{s for s in x["schools"].split(" | ") if s} for x in members])),
            "countries": " | ".join(sorted(set().union(*[{c for c in x["countries"].split(" | ") if c} for x in members]))),
            "semantic_definition": members[0]["semantic_reason"], "demand_mapping_relevance": relevance,
            "manual_decision": "REVIEW_REQUIRED", "manual_note": "",
        })
    summary_fields = list(summaries[0])
    write_csv(OUT / "event_subtype_summary.csv", summary_fields, summaries)

    by_type = defaultdict(list)
    for s in summaries: by_type[s["event_type"]].append(s)
    lines = ["# Academic Calendar Event Subtype Manual Review V1", "", "Candidate-only review. No subtype is approved or frozen by this artifact. All mappings require manual confirmation.", "", f"- Input records: {len(rows)}", f"- `ACADEMIC_EVENT` records in scope: {len(included)}", f"- `PERIOD_METADATA` excluded: {len(excluded)}", f"- Unique raw events in scope: {len(details)}", ""]
    for etype in sorted(by_type):
        lines += [f"## {etype}", ""]
        for s in by_type[etype]:
            lines += [f"### {s['candidate_event_subtype']}", "", f"- Definition: {s['semantic_definition']}", f"- Raw events / records: {s['raw_event_count']} / {s['record_count']}", f"- Schools: {s['school_count']}; countries: {s['countries']}", f"- Demand Mapping relevance: {s['demand_mapping_relevance']}", "- Manual decision: REVIEW_REQUIRED", "", "Raw official events:", ""]
            for d in [x for x in details if x['event_type'] == etype and x['candidate_event_subtype'] == s['candidate_event_subtype']]:
                lines.append(f"- `{d['event_name_original']}` — {d['record_count']} record(s); {d['schools']}; issue: {d['potential_semantic_issue']}")
            lines.append("")
    lines += ["## Excluded Period Metadata", "", "The following two records are intentionally excluded from event subtype taxonomy and future Demand Mapping:", ""]
    for r in excluded:
        lines.append(f"- `{r['event_name_original']}` — {r['school']} ({r['country']}), period `{r['period_type']} / {r['period_name']}`")
    (OUT / "event_subtype_manual_review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    counts_by_rel_raw = Counter(d["demand_mapping_relevance"] for d in details)
    counts_by_rel_records = Counter()
    for d in details: counts_by_rel_records[d["demand_mapping_relevance"]] += int(d["record_count"])
    report = {
        "artifact": "academic_calendar_event_subtype_review_v1", "status": "CANDIDATE_REVIEW_REQUIRED_NOT_FROZEN",
        "source": str(SOURCE.relative_to(ROOT)), "source_records": len(rows),
        "unique_raw_event_names_total": len({r['event_name_original'] for r in rows}),
        "period_metadata": {"record_count": len(excluded), "unique_raw_event_names": len({r['event_name_original'] for r in excluded}), "excluded_from_subtype_taxonomy": True},
        "taxonomy_scope": {"record_count": len(included), "unique_raw_event_names": len(details), "candidate_subtype_count": len(summaries)},
        "demand_mapping_relevance": {"unique_raw_event_counts": dict(counts_by_rel_raw), "record_counts": dict(counts_by_rel_records)},
        "manual_decision": "REVIEW_REQUIRED for every candidate mapping", "demand_mapping_executed": False, "opportunity_generation_executed": False,
    }
    (OUT / "event_subtype_review_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
