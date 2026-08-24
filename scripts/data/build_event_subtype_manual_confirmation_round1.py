#!/usr/bin/env python3
"""Prepare (only) the Event Subtype Manual Confirmation Round 1 review."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_event_subtype_review"
OUT = SRC


def recommendation(etype, subtype):
    # Recommendation is deliberately non-operative. Human decision remains REVIEW_REQUIRED.
    merges = {
        "ARRIVAL": "ORIENTATION_PERIOD", "INDUCTION_WEEK": "ORIENTATION_PERIOD",
        "INTERNATIONAL_ORIENTATION": "ORIENTATION_PERIOD", "WELCOME_WEEK": "ORIENTATION_PERIOD",
        "FALL_BREAK": "ACADEMIC_BREAK", "GENERAL_BREAK": "ACADEMIC_BREAK",
        "HOLIDAY_BREAK": "ACADEMIC_BREAK", "INTERSEMESTER_BREAK": "ACADEMIC_BREAK",
        "MID_SEMESTER_BREAK": "ACADEMIC_BREAK", "TEACHING_BREAK": "ACADEMIC_BREAK",
        "READING_AND_FIELD_TRIP": "READING_WEEK",
        "CHRISTMAS_VACATION": "VACATION_PERIOD", "SUMMER_VACATION": "VACATION_PERIOD",
        "WINTER_VACATION": "VACATION_PERIOD",
    }
    if subtype in merges:
        return "MERGE", f"Candidate to merge into {merges[subtype]}; the preserved original name/date retain the narrower official wording."
    if subtype == "FINAL_ASSESSMENT":
        return "MOVE_PARENT", "Official wording is assessment rather than examination; review move from EXAM to ASSESSMENT without changing this Round 1 source."
    if subtype == "DEFERRED_EXAM":
        return "REVIEW_REQUIRED", "A deferred examination can be administratively related to resit but is not necessarily a resit; human parent-category confirmation required."
    if subtype == "TEACHING_START":
        return "REVIEW_REQUIRED", "Raw terms mix intake labels, classes and teaching resumption; confirm they are one stable start semantic."
    if subtype == "POST_INTAKE_BREAK":
        return "REVIEW_REQUIRED", "May be programme/intake administration rather than a reusable academic-break semantic."
    return "KEEP", "Current subtype adds stable semantic information beyond its parent event_type."


def direct_assessment(row):
    """Strictly assess existing DIRECT only; no data is changed."""
    st = row["candidate_event_subtype"]
    if st in {"GENERAL_EXAM", "FINAL_EXAM", "RESIT_EXAM", "SUPPLEMENTARY_EXAM", "DEFERRED_EXAM"}:
        why = "Official wording identifies an examination or a named examination pathway that can directly signal an exam-related demand context."
        task = "考试" if st in {"GENERAL_EXAM", "FINAL_EXAM", "DEFERRED_EXAM"} else "补考"
        issue = "DEFERRED_EXAM still needs parent-category confirmation." if st == "DEFERRED_EXAM" else "NONE"
        return why, task, "STRONG", "DIRECT", issue
    if st in {"EXAM_AND_ASSESSMENT", "ASSESSMENT_AND_EXAM", "REVISION_AND_EXAM"}:
        return ("A confirmed composite official event contains an explicit examination component, but cannot on its own choose a single downstream task type.",
                "考试（复合事件）", "MEDIUM", "DIRECT", "Use only a constrained composite-exam signal; never split it into invented records.")
    if st == "FINAL_ASSESSMENT":
        return ("It denotes an assessment endpoint, but does not by itself identify a specific task type and its parent EXAM is under review.",
                "", "MEDIUM", "CONTEXTUAL", "Recommend downgrade until parent and mapping semantics are manually confirmed.")
    if st == "ASSESSMENT_PERIOD":
        return ("It identifies an assessment phase but not a concrete service/task type.", "", "MEDIUM", "CONTEXTUAL", "Assessment timing alone is contextual.")
    if st == "TEACHING_AND_ASSESSMENT":
        return ("It identifies a mixed teaching and assessment phase, not a single task type.", "", "MEDIUM", "CONTEXTUAL", "Mixed phase should not directly infer demand.")
    if st == "REVISION_PERIOD":
        return ("It identifies preparation timing only; no specific task type is established by the calendar event itself.", "", "MEDIUM", "CONTEXTUAL", "Revision period is contextual, not direct.")
    raise ValueError(st)


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)


def main():
    with (SRC / "event_subtype_summary.csv").open(encoding="utf-8-sig", newline="") as f:
        summaries = list(csv.DictReader(f))
    with (SRC / "event_subtype_raw_event_mapping.csv").open(encoding="utf-8-sig", newline="") as f:
        details = list(csv.DictReader(f))
    raw_by_subtype = defaultdict(list)
    for r in details: raw_by_subtype[(r["event_type"], r["candidate_event_subtype"])].append(r)

    subtype_rows = []
    conflicts = []
    for s in summaries:
        key = (s["event_type"], s["candidate_event_subtype"])
        raws = raw_by_subtype[key]
        decision, rationale = recommendation(*key)
        issue_list = sorted({r["potential_semantic_issue"] for r in raws if r["potential_semantic_issue"] != "NONE"})
        potential = " | ".join(issue_list) if issue_list else "NONE"
        subtype_rows.append({
            "event_type": s["event_type"], "event_subtype": s["candidate_event_subtype"],
            "semantic_definition": s["semantic_definition"], "raw_event_count": s["raw_event_count"],
            "record_count": s["record_count"], "school_count": s["school_count"], "countries": s["countries"],
            "event_name_original_all": " | ".join(r["event_name_original"] for r in raws),
            "current_demand_mapping_relevance": s["demand_mapping_relevance"], "potential_issue": potential,
            "recommended_decision": decision, "recommendation_reason": rationale,
            "manual_decision": "REVIEW_REQUIRED", "manual_note": "",
        })
        if potential != "NONE" or decision != "KEEP":
            conflicts.append({"event_type": s["event_type"], "event_subtype": s["candidate_event_subtype"],
                              "issue_type": "SEMANTIC_OR_TAXONOMY_REVIEW", "potential_issue": potential,
                              "recommended_decision": decision, "recommendation_reason": rationale,
                              "manual_decision": "REVIEW_REQUIRED", "manual_note": ""})
    fields = list(subtype_rows[0]); write_csv(OUT / "subtype_manual_confirmation_round1.csv", fields, subtype_rows)
    write_csv(OUT / "subtype_semantic_conflict_review.csv", list(conflicts[0]), conflicts)

    direct_rows = []
    for d in details:
        if d["demand_mapping_relevance"] != "DIRECT": continue
        why, task, strength, rec_rel, issue = direct_assessment(d)
        direct_rows.append({
            "event_type": d["event_type"], "event_subtype": d["candidate_event_subtype"],
            "event_name_original": d["event_name_original"], "record_count": d["record_count"],
            "school": d["schools"], "country": d["countries"], "current_relevance": "DIRECT",
            "why_direct": why, "potential_task_type_if_any": task,
            "direct_semantic_strength": strength, "recommended_relevance": rec_rel,
            "potential_issue": issue, "manual_decision": "REVIEW_REQUIRED", "manual_note": "",
        })
    write_csv(OUT / "direct_relevance_manual_review.csv", list(direct_rows[0]), direct_rows)

    by_type = defaultdict(list)
    for r in subtype_rows: by_type[r["event_type"]].append(r)
    lines = ["# Event Subtype Manual Confirmation Round 1", "", "This is an approval-preparation artifact only. It does not modify the frozen calendar, event types, event subtypes, or any Demand Mapping behavior.", "", "## Decision summary", ""]
    for decision in ["KEEP", "MERGE", "RENAME", "MOVE_PARENT", "SPLIT", "REVIEW_REQUIRED"]:
        lines.append(f"- Recommended {decision}: {sum(r['recommended_decision'] == decision for r in subtype_rows)} subtype(s)")
    lines += ["", "## Candidate subtype review", ""]
    for etype in sorted(by_type):
        lines += [f"### {etype}", ""]
        for r in by_type[etype]:
            lines += [f"#### {r['event_subtype']}", "", f"- Raw events / records: {r['raw_event_count']} / {r['record_count']}", f"- Definition: {r['semantic_definition']}", f"- Relevance: {r['current_demand_mapping_relevance']}", f"- Potential issue: {r['potential_issue']}", f"- Recommended decision: {r['recommended_decision']} — {r['recommendation_reason']}", "- Manual decision: REVIEW_REQUIRED", "", "Official raw events:", ""]
            for d in raw_by_subtype[(etype, r['event_subtype'])]:
                lines.append(f"- `{d['event_name_original']}` — {d['record_count']} record(s); schools: {d['schools']}; countries: {d['countries']}")
            lines.append("")
    lines += ["## Strict audit of the current DIRECT candidates", "", "The following table contains all 32 unique raw events currently marked DIRECT. A recommendation of CONTEXTUAL means the event alone does not prove one concrete downstream task type.", "", "| Event subtype | Raw event | Strength | Recommended relevance | Potential task type |", "|---|---|---|---|---|"]
    for r in direct_rows:
        lines.append(f"| {r['event_subtype']} | {r['event_name_original']} | {r['direct_semantic_strength']} | {r['recommended_relevance']} | {r['potential_task_type_if_any'] or '—'} |")
    (OUT / "event_subtype_manual_confirmation_round1.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print({"candidate_subtypes": len(subtype_rows), "direct_raw_events": len(direct_rows),
           "recommended": {x: sum(r['recommended_decision'] == x for r in subtype_rows) for x in ['KEEP','MERGE','RENAME','MOVE_PARENT','SPLIT','REVIEW_REQUIRED']},
           "direct_strength": {x: sum(r['direct_semantic_strength'] == x for r in direct_rows) for x in ['STRONG','MEDIUM','WEAK']},
           "direct_relevance_recommendation": {x: sum(r['recommended_relevance'] == x for r in direct_rows) for x in ['DIRECT','CONTEXTUAL','NONE','REVIEW_REQUIRED']}})


if __name__ == "__main__":
    main()
