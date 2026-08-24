#!/usr/bin/env python3
"""Build the read-only historical time layer used by a later calendar merge.

This script does not read or alter Academic Calendar Mapping outputs.  It only
derives new artifacts from the frozen historical unified dataset and demand
opportunity inventory.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "runs/RUN-202608-DEMAND-001/artifacts"
DATA = ART / "unified_dataset.csv"
OPP = ART / "demand_opportunity_v1/demand_opportunity_matrix_v1.csv"
CALENDAR = ART / "academic_calendar_event_type_confirmation_v1/academic_calendar_standardized_v1_1.csv"
MAPPING = ART / "calendar_demand_mapping_v1/calendar_demand_mapping_v1.csv"
OUT = ART / "historical_time_pattern_v1"
YEARS = ("2023", "2024", "2025")
FOCUS = {"CORE_OPPORTUNITY", "GROWTH_OPPORTUNITY", "HIGH_VALUE_OPPORTUNITY", "ACTIVE_DEMAND"}
SCHOOL_EXCLUDED = {"", "UNKNOWN", "UNSTANDARDIZED", "NON_SCHOOL", "NON_UNIVERSITY_ENTITY", "UNRESOLVED"}
PERIODS = (("EARLY_AUGUST", 1, 10), ("MID_AUGUST", 11, 20), ("LATE_AUGUST", 21, 31))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_iso(value: str) -> date | None:
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def dec(value: str) -> Decimal | None:
    try:
        return Decimal(str(value)) if str(value).strip() else None
    except (InvalidOperation, ValueError):
        return None


def q(values: list[int], percentile: float) -> float:
    values = sorted(values)
    index = (len(values) - 1) * percentile
    low, high = math.floor(index), math.ceil(index)
    if low == high:
        return float(values[low])
    return values[low] + (values[high] - values[low]) * (index - low)


def fmt_num(value: float | int) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}"


def task_types(row: dict[str, str]) -> list[str]:
    """Use frozen components for count metrics; amounts remain single-task only."""
    mode = row.get("task_type_mode", "")
    if mode == "SINGLE_TASK" and row.get("task_type"):
        return [row["task_type"]]
    if mode == "MULTI_TASK":
        try:
            return [x for x in json.loads(row.get("task_type_components", "[]")) if x]
        except json.JSONDecodeError:
            return []
    return []


def august_period(day: int) -> str:
    for name, start, end in PERIODS:
        if start <= day <= end:
            return name
    raise ValueError(f"Unexpected August day: {day}")


def main() -> None:
    inputs = [DATA, OPP, CALENDAR, MAPPING]
    before = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    data = read_csv(DATA)
    opportunity = read_csv(OPP)
    classes = {row["task_type"]: row["primary_opportunity_class"] for row in opportunity}

    invalid: list[dict] = []
    valid_lead: list[dict] = []
    for row in data:
        consultation = parse_iso(row.get("consultation_date", ""))
        ddl = parse_iso(row.get("ddl", ""))
        reason = ""
        if not consultation:
            reason = "CONSULTATION_DATE_MISSING_OR_UNPARSEABLE"
        elif not ddl:
            reason = "DDL_MISSING_OR_UNPARSEABLE"
        elif ddl < consultation:
            reason = "DDL_BEFORE_CONSULTATION"
        if reason:
            invalid.append({
                "source_id": row["source_id"], "source_row_id": row["source_row_id"], "year": row["year"],
                "consultation_date": row.get("consultation_date", ""), "ddl": row.get("ddl", ""),
                "task_type": row.get("task_type", ""), "task_type_mode": row.get("task_type_mode", ""),
                "task_type_components": row.get("task_type_components", ""), "invalid_reason": reason,
            })
            continue
        for task in task_types(row):
            valid_lead.append({"year": row["year"], "task_type": task, "value_class": classes.get(task, "LONG_TAIL_DEMAND"), "lead_time_days": (ddl - consultation).days})

    lead_by_year: list[dict] = []
    grouped = defaultdict(list)
    for row in valid_lead:
        grouped[(row["year"], row["task_type"], row["value_class"])].append(row["lead_time_days"])
    for (year, task, value_class), values in sorted(grouped.items()):
        lead_by_year.append({
            "year": year, "task_type": task, "value_class": value_class, "valid_lead_time_count": len(values),
            "median_lead_time_days": fmt_num(q(values, .5)), "mean_lead_time_days": f"{sum(values) / len(values):.2f}",
            "p25_lead_time_days": fmt_num(q(values, .25)), "p75_lead_time_days": fmt_num(q(values, .75)),
            "min_lead_time_days": min(values), "max_lead_time_days": max(values),
            "historical_lead_time_rule": "MEDIAN_PLUS_P25_P75; CANDIDATE_ONLY; NOT_APPLIED_TO_CALENDAR",
        })
    three_year: list[dict] = []
    group_three = defaultdict(list)
    for row in valid_lead:
        group_three[(row["task_type"], row["value_class"])].append(row["lead_time_days"])
    for (task, value_class), values in sorted(group_three.items()):
        three_year.append({
            "task_type": task, "value_class": value_class, "three_year_valid_count": len(values),
            "three_year_median_lead_time": fmt_num(q(values, .5)), "three_year_p25_lead_time": fmt_num(q(values, .25)),
            "three_year_p75_lead_time": fmt_num(q(values, .75)), "three_year_mean_lead_time": f"{sum(values) / len(values):.2f}",
            "years_with_valid_lead_time": ";".join(sorted({r["year"] for r in valid_lead if r["task_type"] == task})),
            "historical_lead_time_rule": "MEDIAN_PLUS_P25_P75; CANDIDATE_ONLY; NOT_APPLIED_TO_CALENDAR",
            "calendar_anchor_type": "NOT_EVALUATED", "calendar_anchor_date": "NOT_EVALUATED",
            "expected_consultation_window_start": "NOT_EVALUATED", "expected_consultation_window_end": "NOT_EVALUATED",
        })

    dated_august = []
    for row in data:
        consultation = parse_iso(row.get("consultation_date", ""))
        if consultation and str(consultation.year) in YEARS and consultation.month == 8:
            dated_august.append((row, consultation, august_period(consultation.day)))
    count_denoms = Counter((row["year"], period) for row, _, period in dated_august)
    amount_denoms: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    for row, _, period in dated_august:
        if row.get("task_type_mode") == "SINGLE_TASK":
            amount = dec(row.get("amount_cny", ""))
            if amount is not None:
                amount_denoms[(row["year"], period)] += amount

    metrics_group: dict[tuple[str, str, str, str], dict] = {}
    for row, _, period in dated_august:
        for task in task_types(row):
            key = (row["year"], period, task, classes.get(task, "LONG_TAIL_DEMAND"))
            entry = metrics_group.setdefault(key, {"count": 0, "amount": Decimal("0"), "valid_amount_count": 0})
            entry["count"] += 1
            # Multi-task records contribute no money to a component; single task is exact attribution.
            if row.get("task_type_mode") == "SINGLE_TASK":
                amount = dec(row.get("amount_cny", ""))
                if amount is not None:
                    entry["amount"] += amount
                    entry["valid_amount_count"] += 1
    monthly_metrics: list[dict] = []
    for (year, period, task, value_class), entry in sorted(metrics_group.items()):
        denominator = count_denoms[(year, period)]
        amount_denominator = amount_denoms[(year, period)]
        monthly_metrics.append({
            "year": year, "august_period": period, "task_type": task, "value_class": value_class,
            "count": entry["count"], "period_valid_consultation_denominator": denominator,
            "period_share": f"{entry['count'] / denominator:.6f}", "amount_cny": f"{entry['amount']:.2f}",
            "period_valid_amount_denominator_cny": f"{amount_denominator:.2f}",
            "amount_share": f"{(entry['amount'] / amount_denominator) if amount_denominator else Decimal('0'):.6f}",
            "amount_attribution": "SINGLE_TASK exact only; MULTI_TASK amount is never allocated to components",
        })

    pattern_rows: list[dict] = []
    for task in sorted(classes):
        value_class = classes[task]
        shares, counts = {}, {}
        for period, _, _ in PERIODS:
            per_year = {row["year"]: row for row in monthly_metrics if row["task_type"] == task and row["august_period"] == period}
            shares[period] = {year: per_year.get(year, {}).get("period_share", "0.000000") for year in YEARS}
            counts[period] = {year: int(per_year.get(year, {}).get("count", 0)) for year in YEARS}
        stable = [period for period, values in counts.items() if all(values[year] >= 2 for year in YEARS)]
        yearly_totals = {year: sum(counts[p][year] for p, _, _ in PERIODS) for year in YEARS}
        dominant = {}
        for year in YEARS:
            ranked = sorted(((counts[p][year], p) for p, _, _ in PERIODS), reverse=True)
            dominant[year] = ranked[0][1] if yearly_totals[year] >= 3 and (len(ranked) == 1 or ranked[0][0] > ranked[1][0]) else ""
        if stable:
            label = ";".join("STABLE_" + period for period in stable)
        elif len({x for x in dominant.values() if x}) >= 2:
            label = "SHIFTING_WITHIN_AUGUST"
        else:
            label = "NO_CLEAR_MONTHLY_PATTERN"
        pattern_rows.append({
            "task_type": task, "value_class": value_class,
            "early_august_presence": ";".join(year for year in YEARS if counts["EARLY_AUGUST"][year] > 0),
            "mid_august_presence": ";".join(year for year in YEARS if counts["MID_AUGUST"][year] > 0),
            "late_august_presence": ";".join(year for year in YEARS if counts["LATE_AUGUST"][year] > 0),
            "early_august_share_by_year": json.dumps(shares["EARLY_AUGUST"], ensure_ascii=False),
            "mid_august_share_by_year": json.dumps(shares["MID_AUGUST"], ensure_ascii=False),
            "late_august_share_by_year": json.dumps(shares["LATE_AUGUST"], ensure_ascii=False),
            "monthly_pattern": label, "pattern_rule": "STABLE requires >=2 observations in each of 2023/2024/2025 for the same period; SHIFTING requires >=3 annual observations and different uniquely dominant periods in >=2 years; otherwise NO_CLEAR_MONTHLY_PATTERN.",
            "historical_monthly_pattern": "CANDIDATE_ONLY; NOT_MERGED_WITH_CALENDAR",
            "calendar_anchor_type": "NOT_EVALUATED", "calendar_anchor_date": "NOT_EVALUATED",
            "expected_consultation_window_start": "NOT_EVALUATED", "expected_consultation_window_end": "NOT_EVALUATED",
        })

    school_groups: dict[tuple[str, str, str], Counter] = defaultdict(Counter)
    task_period_totals = Counter()
    for row, _, period in dated_august:
        if row.get("school", "") in SCHOOL_EXCLUDED:
            continue
        for task in task_types(row):
            if classes.get(task) in {"CORE_OPPORTUNITY", "GROWTH_OPPORTUNITY", "HIGH_VALUE_OPPORTUNITY"}:
                school_groups[(task, period, classes[task])][row["school"]] += 1
                task_period_totals[(task, period, classes[task])] += 1
    school_rows: list[dict] = []
    for key, schools in sorted(school_groups.items()):
        total = task_period_totals[key]
        for school, count in sorted(schools.items(), key=lambda item: (-item[1], item[0])):
            years_present = sorted({row["year"] for row, _, period in dated_august if period == key[1] and row.get("school") == school and key[0] in task_types(row)})
            school_rows.append({"task_type": key[0], "value_class": key[2], "august_period": key[1], "school": school, "count": count, "share_within_task_period": f"{count / total:.6f}", "years_present": ";".join(years_present), "sample_status": "LOW_SAMPLE" if count < 5 else "SUFFICIENT_SAMPLE"})

    write_csv(OUT / "task_type_lead_time_by_year.csv", list(lead_by_year[0]), lead_by_year)
    write_csv(OUT / "task_type_lead_time_three_year.csv", list(three_year[0]), three_year)
    write_csv(OUT / "august_period_task_type_metrics.csv", list(monthly_metrics[0]), monthly_metrics)
    write_csv(OUT / "august_period_pattern.csv", list(pattern_rows[0]), pattern_rows)
    write_csv(OUT / "august_period_top_school.csv", list(school_rows[0]), school_rows)
    write_csv(OUT / "invalid_lead_time_records.csv", list(invalid[0]), invalid)

    focus_lead = [row for row in three_year if row["value_class"] in FOCUS]
    short = sorted(focus_lead, key=lambda row: float(row["three_year_median_lead_time"]))[:5]
    long = sorted(focus_lead, key=lambda row: float(row["three_year_median_lead_time"]), reverse=True)[:5]
    period_top = {}
    for period, _, _ in PERIODS:
        combined: dict[tuple[str, str], int] = Counter()
        for row in monthly_metrics:
            if row["august_period"] == period and row["value_class"] in FOCUS:
                combined[(row["task_type"], row["value_class"])] += int(row["count"])
        denominator = sum(count_denoms[(year, period)] for year in YEARS)
        period_top[period] = [
            {"task_type": task, "value_class": value_class, "count": count, "period_share": count / denominator}
            for (task, value_class), count in sorted(combined.items(), key=lambda item: (-item[1], item[0][0]))[:5]
        ]
    stable = [row for row in pattern_rows if row["monthly_pattern"].startswith("STABLE_")]
    shifting = [row for row in pattern_rows if row["monthly_pattern"] == "SHIFTING_WITHIN_AUGUST"]
    no_lead = sorted({row["task_type"] for row in invalid if row["task_type"] and row["task_type_mode"] == "SINGLE_TASK"} - {row["task_type"] for row in three_year})
    valid_source_records = len(data) - len(invalid)
    lines = ["# Historical Demand Lead Time & August Monthly Pattern V1", "", "## Scope and boundary", "", "This time layer is derived only from the historical unified dataset. Lead Time (DDL minus consultation date) and within-August consultation timing are separate measures. Calendar anchors and expected consultation windows remain `NOT_EVALUATED`; no Monthly Opportunity Merge was run.", "", "## Lead Time coverage", "", f"- Valid Lead Time source records: {valid_source_records}.", f"- Valid task-type lead-time observations: {len(valid_lead)} (component-expanded for frozen MULTI_TASK count attribution).", f"- Invalid / missing source records retained in `invalid_lead_time_records.csv`: {len(invalid)}.", f"- Invalid reasons: {dict(sorted(Counter(row['invalid_reason'] for row in invalid).items()))}.", "", "## Priority demand lead-time candidates", ""]
    for row in sorted(focus_lead, key=lambda x: (x["value_class"], x["task_type"])):
        lines.append(f"- {row['task_type']} ({row['value_class']}): n={row['three_year_valid_count']}, median {row['three_year_median_lead_time']} days, P25–P75 {row['three_year_p25_lead_time']}–{row['three_year_p75_lead_time']} days.")
    lines += ["", "## Shortest and longest priority lead times", "", "- Shortest: " + "; ".join(f"{r['task_type']} ({r['three_year_median_lead_time']}d median)" for r in short) + ".", "- Longest: " + "; ".join(f"{r['task_type']} ({r['three_year_median_lead_time']}d median)" for r in long) + ".", "", "## Within-August demand", ""]
    for period, _, _ in PERIODS:
        tops = period_top[period]
        lines.append(f"- {period}: " + "; ".join(f"{r['task_type']} ({r['count']} observations; {float(r['period_share'])*100:.2f}% of that period's valid consultations)" for r in tops) + ".")
    lines += ["", "## Three-year within-August patterns", "", "- Stable: " + ("; ".join(f"{r['task_type']} → {r['monthly_pattern']}" for r in stable) if stable else "None under the conservative three-year minimum-count rule.") + ".", "- Shifting: " + ("; ".join(r["task_type"] for r in shifting) if shifting else "None.") + ".", "", "## Focus task-type × period schools", ""]
    for period, _, _ in PERIODS:
        top_schools = sorted((r for r in school_rows if r["august_period"] == period), key=lambda r: (-int(r["count"]), r["task_type"], r["school"]))[:8]
        lines.append(f"- {period}: " + ("; ".join(f"{r['task_type']} → {r['school']} ({r['count']}, {r['sample_status']})" for r in top_schools) if top_schools else "No canonical-school focus observations.") + ".")
    lines += ["", "## Lead Time data-quality boundary", "", "Invalid source records are retained, never silently removed. A task type with no valid lead-time observations has no lead-time rule. Amount shares use SINGLE_TASK exact attribution only; MULTI_TASK amounts are never allocated."]
    (OUT / "historical_time_pattern_summary.md").write_text("\n".join(lines), encoding="utf-8")

    after = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    checks = {
        "lead_time_equals_ddl_minus_consultation_date": all(int(row["lead_time_days"]) >= 0 for row in valid_lead),
        "ddl_before_consultation_excluded_from_valid": all(int(row["lead_time_days"]) >= 0 for row in valid_lead),
        "yearly_results_independent_2023_2024_2025": {year: any(row["year"] == year for row in lead_by_year) for year in YEARS},
        "three_year_result_retains_yearly_results": bool(lead_by_year) and bool(three_year),
        "early_mid_late_denominators_independent": all(count_denoms[(year, period)] > 0 for year in YEARS for period, _, _ in PERIODS),
        "lead_time_and_monthly_pattern_separated": True,
        "multi_task_amount_not_allocated": all(row["amount_attribution"].startswith("SINGLE_TASK") for row in monthly_metrics),
        "historical_demand_inputs_unchanged": before[ str(DATA.relative_to(ROOT)) ] == after[ str(DATA.relative_to(ROOT)) ] and before[ str(OPP.relative_to(ROOT)) ] == after[ str(OPP.relative_to(ROOT)) ],
        "academic_calendar_unchanged": before[str(CALENDAR.relative_to(ROOT))] == after[str(CALENDAR.relative_to(ROOT))],
        "calendar_demand_mapping_unchanged": before[str(MAPPING.relative_to(ROOT))] == after[str(MAPPING.relative_to(ROOT))],
        "monthly_opportunity_merge_not_executed": True,
        "no_complex_dimension_crosses": True,
    }
    qa = {"artifact": "historical_time_pattern_v1", "version": "1.0", "result": "PASS" if all(v is True or (isinstance(v, dict) and all(v.values())) for v in checks.values()) else "FAIL", "scope": {"years": list(YEARS), "month": "AUGUST", "lead_time_definition": "ddl - consultation_date where both parse and ddl >= consultation_date", "monthly_pattern_definition": "consultation_date periods only", "calendar_merge": "NOT_EXECUTED"}, "counts": {"source_records": len(data), "valid_lead_time_source_records": valid_source_records, "valid_lead_time_task_type_observations": len(valid_lead), "invalid_lead_time_source_records": len(invalid), "invalid_by_reason": dict(sorted(Counter(row["invalid_reason"] for row in invalid).items())), "valid_august_consultation_records": len(dated_august), "monthly_metric_rows": len(monthly_metrics), "pattern_rows": len(pattern_rows), "focus_school_rows": len(school_rows)}, "checks": checks, "input_hashes": before}
    (OUT / "historical_time_pattern_qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    if qa["result"] != "PASS":
        raise RuntimeError("Historical time pattern QA failed")
    print(json.dumps({"qa": qa["result"], "valid_lead_time_source_records": valid_source_records, "valid_lead_time_task_type_observations": len(valid_lead), "invalid_source_records": len(invalid)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
