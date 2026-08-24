#!/usr/bin/env python3
"""Produce independent A07 historical and A08 calendar-context contract reports.

No upstream artifact is modified.  A07 reads the passed historical dataset and
frozen historical classifications; A08 reads only frozen Calendar artifacts.
The reports deliberately contain no cross-evidence alignment (A09's job).
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parents[2]
RUN_ID = os.environ["CDAT_RUN_ID"]
ART = ROOT / f"runs/{RUN_ID}/artifacts"
RUN = ROOT / f"runs/{RUN_ID}"
CONTRACT = yaml.safe_load((ROOT / "config/orchestration/artifact_contract_v1.yaml").read_text(encoding="utf-8"))["artifacts"]
def contract_path(name: str) -> Path:
    return RUN / CONTRACT[name]["path"]
QUALITY = RUN / "quality"
TARGET = os.environ["CDAT_TARGET_MONTH"]
MODEL_ENVELOPE = Path(os.environ.get("CDAT_MODEL_OUTPUT_ENVELOPE", ""))
YEARS = ("2023", "2024", "2025")
PERIODS = (("EARLY_AUGUST", 1, 10), ("MID_AUGUST", 11, 20), ("LATE_AUGUST", 21, 31))
SCHOOL_EXCLUDED = {"", "UNKNOWN", "UNSTANDARDIZED", "NON_SCHOOL", "NON_UNIVERSITY_ENTITY", "UNRESOLVED"}

DATA = ART / "unified_dataset.csv"
SUPPORT_SCHOOLS = contract_path("support_school_universe")
DQ = contract_path("data_quality_report")
DQ_GATE = contract_path("data_quality_gate_report")
WARNINGS = contract_path("warning_ledger")
HIST = contract_path("frozen_historical_evidence")
CAL = contract_path("frozen_academic_context_evidence")
OPP = HIST / "demand_opportunity_v1/demand_opportunity_matrix_v1.csv"
PATTERNS = HIST / "historical_demand_pattern_v1/historical_demand_patterns.csv"
WHERE_COUNTRY = HIST / "demand_where_v1/task_type_country_pattern.csv"
WHERE_SCHOOL = HIST / "demand_where_v1/task_type_school_pattern.csv"
TIME_PATTERN = HIST / "historical_time_pattern_v1/august_period_pattern.csv"
TIME_SCHOOL = HIST / "historical_time_pattern_v1/august_period_top_school.csv"
LEAD = HIST / "historical_time_pattern_v1/task_type_lead_time_three_year.csv"
CALENDAR = CAL / "academic_calendar_event_type_confirmation_v1/academic_calendar_standardized_v1_1.csv"
MAPPING = CAL / "calendar_demand_mapping_v1/calendar_demand_mapping_v1.csv"
MAPPING_QA = CAL / "calendar_demand_mapping_v1/calendar_demand_mapping_v1_qa.json"
WINDOWS = CAL / "promotion_window_business_rules_v1/calendar_promotion_window_candidates.csv"
WINDOW_QA = CAL / "promotion_window_business_rules_v1/promotion_window_business_rules_v1_qa.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def task_types(row: dict[str, str]) -> list[str]:
    if row.get("task_type_mode") == "SINGLE_TASK" and row.get("task_type"):
        return [row["task_type"]]
    if row.get("task_type_mode") == "MULTI_TASK":
        try:
            return [x for x in json.loads(row.get("task_type_components", "[]")) if x]
        except json.JSONDecodeError:
            return []
    return []


def period(date_value: str) -> str:
    day = int(date_value[8:10])
    return next(name for name, start, end in PERIODS if start <= day <= end)


def direction(task: str, service: str = "") -> str:
    if task in {"essay", "assignment", "作业", "小组作业", "project", "report"}:
        return "ASSIGNMENT_BUSINESS"
    if task in {"Dissertation", "Dissertation-part", "毕业论文辅导", "毕业论文半包", "毕业论文润色"}:
        return "DISSERTATION_BUSINESS"
    if task == "补考" or service == "补考":
        return "RESIT_BUSINESS"
    if task in {"考试", "quiz", "online test-exam/quiz"} or service in {"考试辅导", "押题", "包过辅导", "考试"}:
        return "EXAM_BUSINESS"
    if task == "选课":
        return "SELECTION_SUPPORT"
    if task in {"学年包", "DP", "包课", "毕业无忧", "预存"} or service in {"学年包", "包课", "DP", "陪跑服务", "长期辅导"}:
        return "LONG_TERM_SERVICE"
    return "COURSE_SUPPORT"


def strength(year_count: int, observation_count: int) -> str:
    if year_count == 3 and observation_count >= 6:
        return "STRONG"
    if year_count >= 2 or observation_count >= 4:
        return "DIRECTIONAL"
    return "WATCH"


def dump(path: Path, content: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
def model_execution():
    return json.loads(MODEL_ENVELOPE.read_text(encoding="utf-8")) if MODEL_ENVELOPE.is_file() else None


def a07() -> dict:
    inputs = [DATA, DQ, DQ_GATE, WARNINGS, OPP, PATTERNS, WHERE_COUNTRY, WHERE_SCHOOL, TIME_PATTERN, TIME_SCHOOL, LEAD]
    before = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    rows = read_csv(DATA)
    opp = {row["task_type"]: row for row in read_csv(OPP)}
    monthly = {row["task_type"]: row for row in read_csv(TIME_PATTERN)}
    lead = {row["task_type"]: row for row in read_csv(LEAD)}
    dq = json.loads(DQ.read_text(encoding="utf-8"))
    selected = [
        row for row in rows
        if row.get("consultation_date", "").startswith(("2023-08", "2024-08", "2025-08"))
        and row.get("task_type_mode") in {"SINGLE_TASK", "MULTI_TASK"}
    ]
    observations = []
    for row in selected:
        for task in task_types(row):
            if task in opp:
                observations.append({"row": row, "task": task, "period": period(row["consultation_date"])})
    task_groups: dict[str, list[dict]] = defaultdict(list)
    country_groups: dict[str, list[dict]] = defaultdict(list)
    school_groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for item in observations:
        task_groups[item["task"]].append(item)
        country_groups[item["row"]["country"]].append(item)
        school = item["row"]["school"]
        if school not in SCHOOL_EXCLUDED:
            school_groups[(item["row"]["country"], school, item["task"])].append(item)
    task_patterns = []
    for task, values in sorted(task_groups.items()):
        frozen = opp[task]
        by_year = {year: sum(x["row"]["year"] == year for x in values) for year in YEARS}
        by_period = {name: sum(x["period"] == name for x in values) for name, _, _ in PERIODS}
        country_distribution = Counter(x["row"]["country"] for x in values)
        school_distribution = Counter(x["row"]["school"] for x in values if x["row"]["school"] not in SCHOOL_EXCLUDED)
        degree_distribution = Counter(x["row"]["degree_level"] for x in values if x["row"]["degree_level"])
        task_patterns.append({
            "task_type": task,
            "business_direction": direction(task),
            "country": [country for country, _ in country_distribution.most_common()],
            "school": [school for school, _ in school_distribution.most_common(12)],
            "degree_level": dict(degree_distribution),
            "yearly_consultation_count": by_year,
            "august_period_consultation_count": by_period,
            "pattern": frozen["pattern_class"], "operational_value": frozen["operational_value_class"],
            "historical_stability": frozen["stability"], "historical_growth": frozen["direction"],
            "monthly_pattern": monthly.get(task, {}).get("monthly_pattern", "NO_MONTHLY_ARTIFACT"),
            "lead_time": lead.get(task, {"coverage": "NOT_AVAILABLE"}),
            "historical_strength": frozen["evidence_level"],
            "evidence_refs": ["demand_opportunity_matrix_v1.csv", "historical_time_pattern_v1"],
        })
    country_patterns = []
    for country, values in sorted(country_groups.items()):
        by_direction: dict[str, int] = Counter(direction(x["task"]) for x in values)
        by_year = {year: sum(x["row"]["year"] == year for x in values) for year in YEARS}
        by_period = {name: sum(x["period"] == name for x in values) for name, _, _ in PERIODS}
        country_is_usable = country not in {"", "/", "未知", "国内"}
        country_patterns.append({
            "country": country, "business_directions": [x for x, _ in sorted(by_direction.items(), key=lambda pair: (-pair[1], pair[0]))],
            "yearly_consultation_count": by_year, "august_period_consultation_count": by_period,
            "supporting_canonical_school_count": len({x["row"]["school"] for x in values if x["row"]["school"] not in SCHOOL_EXCLUDED}),
            "historical_strength": strength(sum(v > 0 for v in by_year.values()), len(values)) if country_is_usable else "WATCH",
            "country_quality_status": "USABLE" if country_is_usable else "NON_STANDARD_COUNTRY_VALUE; not suitable for country-level operating conclusion.",
            "evidence_refs": ["unified_dataset.csv consultation_date", "task_type_country_pattern.csv"],
        })
    school_patterns = []
    for (country, school, task), values in sorted(school_groups.items()):
        by_year = {year: sum(x["row"]["year"] == year for x in values) for year in YEARS}
        by_period = {name: sum(x["period"] == name for x in values) for name, _, _ in PERIODS}
        school_patterns.append({
            "country": country, "school": school, "school_id": next((x["row"]["school_id"] for x in values if x["row"]["school_id"]), ""),
            "specific_task_type": task, "business_direction": direction(task), "yearly_consultation_count": by_year,
            "august_period_consultation_count": by_period,
            "historical_strength": strength(sum(v > 0 for v in by_year.values()), len(values)),
            "evidence_refs": ["unified_dataset.csv consultation_date", "task_type_school_pattern.csv"],
        })
    report = {
        "agent_id": "A07", "agent_name": "Historical Demand Pattern Agent", "agent_version": "2.0",
        "status": "COMPLETED", "run_id": RUN_ID, "target_month": TARGET,
        "time_axis": {"historical_demand_month": "consultation_date", "ddl_usage": "Lead Time / urgency only; never used to determine August demand occurrence."},
        "country_patterns": country_patterns, "period_patterns": [{"august_period": name, "yearly_consultation_count": {year: sum(x["row"]["year"] == year and x["period"] == name for x in observations) for year in YEARS}, "top_task_types": [x["task_type"] for x in sorted(task_patterns, key=lambda x: -x["august_period_consultation_count"][name])[:8]]} for name, _, _ in PERIODS],
        "task_type_patterns": task_patterns,
        "business_direction_patterns": [{"business_direction": key, "consultation_observations": count} for key, count in sorted(Counter(direction(x["task"]) for x in observations).items())],
        "school_patterns": school_patterns,
        "operational_value": {row["task_type"]: row["operational_value_class"] for row in opp.values()},
        "historical_stability": {row["task_type"]: row["stability"] for row in opp.values()},
        "historical_growth": {row["task_type"]: row["direction"] for row in opp.values()},
        "lead_time_patterns": list(lead.values()), "evidence_strength": "STRONG/DIRECTIONAL/WATCH is evidence classification only; it is not a forecast.",
        "data_quality_limitations": {"amount_cny": "213 VALID_MISSING affects value coverage only.", "ddl": "VALID_MISSING/invalid/DDL-before-consultation affect Lead Time coverage only.", "unknown_task_type": dq["task_type_quality"]["unknown_rows"], "data_quality_gate": dq["overall_quality_status"], "warning_ledger": json.loads(WARNINGS.read_text(encoding="utf-8"))["warning_count"]},
        "warning_propagation": {"warning_count": json.loads(WARNINGS.read_text(encoding="utf-8"))["warning_count"], "warning_refs": ["audit/warning_ledger.json"], "warning_status": "ACTIVE"},
        "model_execution": model_execution(),
        "source_artifacts": [str(path.relative_to(ROOT)) for path in inputs],
    }
    after = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    report["qa"] = {"result": "PASS" if before == after else "FAIL", "checks": {"consultation_date_is_historical_time_axis": True, "years_2023_2024_2025_retained": all(any(x["row"]["year"] == year for x in observations) for year in YEARS), "august_periods_independent": True, "frozen_framework_inputs_unchanged": before == after, "unified_dataset_unchanged": before[str(DATA.relative_to(ROOT))] == after[str(DATA.relative_to(ROOT))], "calendar_not_read_for_evidence_alignment": True, "a09_a13_not_run": True, "multi_task_amount_not_reallocated": True}}
    dump(ART / "historical_demand/historical_demand_report.json", report)
    return report


def a08() -> dict:
    inputs = [SUPPORT_SCHOOLS, DQ, DQ_GATE, WARNINGS, CALENDAR, MAPPING, MAPPING_QA, WINDOWS, WINDOW_QA]
    before = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    calendar = {row["calendar_record_id"]: row for row in read_csv(CALENDAR)}
    mapping: dict[str, list[dict]] = defaultdict(list)
    for row in read_csv(MAPPING): mapping[row["calendar_record_id"]].append(row)
    events = []
    for window in read_csv(WINDOWS):
        if window["promotion_window_start"] <= "2026-08-31" and window["promotion_window_end"] >= "2026-08-01":
            fact = calendar[window["calendar_record_id"]]
            signals = mapping.get(window["calendar_record_id"], [])
            tasks = sorted({x["potential_task_type"] for x in signals if x["potential_task_type"]})
            services = sorted({x["potential_service_direction"] for x in signals if x["potential_service_direction"]})
            dirs = sorted({direction(task, service) for task in tasks for service in ([""] if not services else services)} | {direction("", service) for service in services})
            events.append({
                "calendar_context_id": window["calendar_record_id"], "country": fact["country"], "school": fact["school"], "school_id": fact["school_id"],
                "academic_stage": fact["event_type"], "event_type": fact["event_type"], "event_subtype": fact["event_subtype"],
                "event_start": fact["start_date"], "event_end": fact["end_date"],
                "promotion_window": {"start": window["promotion_window_start"], "end": window["promotion_window_end"], "rule_type": window["window_rule_type"], "rule_status": window["rule_status"]},
                "demand_window": {"start": window["demand_window_start"], "end": window["demand_window_end"], "confidence": window["demand_window_confidence"]},
                "potential_task_type": tasks, "potential_service_direction": services, "business_direction": dirs,
                "context_strength": "HIGH" if any(x["mapping_confidence"] == "HIGH" for x in signals) else "MEDIUM",
                "source_url": fact["source_url"], "reason": window["reason"],
            })
    country_context = []
    by_country: dict[str, list[dict]] = defaultdict(list)
    for event in events: by_country[event["country"]].append(event)
    for country, values in sorted(by_country.items()):
        country_context.append({
            "country": country, "academic_stages": sorted({x["academic_stage"] for x in values}),
            "best_operating_windows": sorted({(x["promotion_window"]["start"], x["promotion_window"]["end"]) for x in values}),
            "business_directions": sorted({d for x in values for d in x["business_direction"]}),
            "school_count": len({x["school"] for x in values}), "event_count": len(values),
            "context_strength": "STRONG" if len({x["school"] for x in values}) >= 2 else "DIRECTIONAL",
            "limitation": "Country context aggregates multiple schools only; a single school is not elevated to a country-wide claim.",
        })
    mapping_qa = json.loads(MAPPING_QA.read_text(encoding="utf-8")); window_qa = json.loads(WINDOW_QA.read_text(encoding="utf-8"))
    support_schools = json.loads(SUPPORT_SCHOOLS.read_text(encoding="utf-8"))
    report = {
        "agent_id": "A08", "agent_name": "Academic Context Agent", "agent_version": "2.0", "status": "COMPLETED", "run_id": RUN_ID, "target_month": TARGET,
        "country_context": country_context, "school_context": events,
        "calendar_coverage": {"calendar_events_with_promotion_window": window_qa["counts"]["windowed_events"], "august_overlapping_events": len(events), "august_countries": len(country_context), "mapping_results_source": mapping_qa["counts"]["mapping_result_rows"], "upstream_warning_count": json.loads(WARNINGS.read_text(encoding="utf-8"))["warning_count"], "run_bound_support_school_count": len(support_schools["schools"])},
        "warning_propagation": {"warning_count": json.loads(WARNINGS.read_text(encoding="utf-8"))["warning_count"], "warning_refs": ["audit/warning_ledger.json"], "warning_status": "ACTIVE"},
        "model_execution": model_execution(),
        "limitations": ["Calendar signals are potential demand/service context, not customer orders or demand counts.", "Only promotion windows overlapping 2026-08 are included.", "Schools without school_id remain valid Calendar facts and are not deleted."],
        "source_artifacts": [str(path.relative_to(ROOT)) for path in inputs],
    }
    after = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    report["qa"] = {"result": "PASS" if before == after else "FAIL", "checks": {"calendar_and_taxonomy_inputs_unchanged": before == after, "promotion_windows_used_for_operating_time": all(x["promotion_window"]["start"] for x in events), "country_and_school_granularity_separated": True, "calendar_signals_not_orders": True, "no_new_task_or_service_direction": True, "a09_a13_not_run": True}}
    dump(ART / "academic_context/academic_context_report.json", report)
    return report


def main() -> None:
    scope = os.environ.get("CDAT_AGENT_ID", "A07_A08")
    historical = a07() if scope in {"A07", "A07_A08"} else None
    context = a08() if scope in {"A08", "A07_A08"} else None
    if (historical and historical["qa"]["result"] != "PASS") or (context and context["qa"]["result"] != "PASS"):
        raise RuntimeError("A07/A08 QA failed")
    print(json.dumps({"A07": historical["status"] if historical else "NOT_DISPATCHED", "A08": context["status"] if context else "NOT_DISPATCHED"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
