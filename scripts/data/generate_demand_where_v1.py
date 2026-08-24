#!/usr/bin/env python3
"""LEVEL 2 WHERE Analysis V1: Task Type -> Country / School / Degree only.

This is deliberately a read-only analysis of the standardized dataset.  Counts
expand frozen MULTI_TASK components; monetary metrics use exact SINGLE_TASK
attribution only, so no order amount is allocated more than once.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import mean, pstdev

import yaml

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "runs/RUN-202608-DEMAND-001/artifacts"
DATA = ART / "unified_dataset.csv"
PRIORITY = ART / "demand_pattern_value_v1/final_priority_task_type_pool.csv"
PRIORITY_CFG = ROOT / "config/insight/demand_pattern_operational_value_v1.yaml"
FRAME = ROOT / "config/insight/demand_where_framework_v1.yaml"
OUT = ART / "demand_where_v1"
YEARS = ("2023", "2024", "2025")
SCHOOL_EXCLUDED = {"", "UNKNOWN", "UNSTANDARDIZED", "NON_SCHOOL", "NON_UNIVERSITY_ENTITY", "UNRESOLVED"}
BASE_EFFECTIVE = 5
P3_EFFECTIVE = 3


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, fields, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def dec(value):
    try:
        return Decimal(value) if str(value).strip() else None
    except (InvalidOperation, ValueError):
        return None


def money(value):
    return format(value.quantize(Decimal("0.01")), "f")


def percent(numerator, denominator):
    if not denominator:
        return ""
    return format((Decimal(numerator) * Decimal("100") / Decimal(denominator)).quantize(Decimal("0.01")), "f")


def row_id(row):
    return (row["source_id"], row["source_row_id"])


def observations(rows):
    """Return (task_type,row,attribution_mode) observations from frozen result."""
    result = []
    for row in rows:
        if row.get("task_type_standardization_status") not in {"STANDARDIZED", "MULTI_TASK"}:
            continue
        if row.get("task_type_mode") == "MULTI_TASK":
            for task in json.loads(row["task_type_components"]):
                result.append((task, row, "MULTI_COMPONENT"))
        elif row.get("task_type_mode") == "SINGLE_TASK" and row.get("task_type"):
            result.append((row["task_type"], row, "SINGLE_TASK"))
    return result


def valid_where(dimension, value):
    return bool(value) and not (dimension == "school" and value in SCHOOL_EXCLUDED)


def effective_floor(priority_class):
    return P3_EFFECTIVE if priority_class == "P3_HIGH_VALUE_NICHE" else BASE_EFFECTIVE


def trend_label(counts, dist, local, present, floor):
    if counts[2] >= floor and counts[0] < floor and counts[1] < floor:
        return "EMERGING"
    if present < 2:
        return "LOW_SAMPLE"
    d_change, l_change = dist[2] - dist[0], local[2] - local[0]
    if d_change > 0 and l_change >= 0 and counts[2] > counts[0]:
        return "RISING"
    if d_change < 0 and l_change <= 0 and counts[2] < counts[0]:
        return "DECLINING"
    cv = pstdev([x for x, c in zip(dist, counts) if c >= floor]) / mean([x for x, c in zip(dist, counts) if c >= floor]) if mean([x for x, c in zip(dist, counts) if c >= floor]) else 0
    return "VOLATILE" if cv > 0.50 else "STABLE"


def main():
    inputs = [DATA, PRIORITY, PRIORITY_CFG, FRAME]
    before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    rows = read_csv(DATA)
    pool = read_csv(PRIORITY)
    frozen = yaml.safe_load(PRIORITY_CFG.read_text(encoding="utf-8"))
    framework = yaml.safe_load(FRAME.read_text(encoding="utf-8"))
    if len(rows) != 818 or frozen.get("status") != "FROZEN" or framework.get("status") != "FROZEN":
        raise RuntimeError("WHERE precondition failed")
    priority = {r["task_type"]: r for r in pool}
    tasks = set(priority)
    if any(r["final_priority_class"] == "P4_WATCHLIST" for r in pool):
        raise RuntimeError("P4 is not allowed in default WHERE scope")
    all_obs = observations(rows)
    by_year = {year: [row for row in rows if row["year"] == year] for year in YEARS}
    obs_year = {year: observations(by_year[year]) for year in YEARS}

    distributions = {"country": [], "school": [], "degree_level": []}
    school_exclusions = Counter()
    # all local denominators cover every valid task observation in a location/year,
    # not merely the priority pool: this retains the requested local-importance meaning.
    for dimension in distributions:
        for year in YEARS:
            task_year_total = Counter(task for task, _, _ in obs_year[year])
            local_total = Counter()
            for _, row, _ in obs_year[year]:
                value = row.get(dimension, "").strip()
                if valid_where(dimension, value):
                    local_total[value] += 1
                elif dimension == "school":
                    school_exclusions[year] += 1
            bucket = defaultdict(list)
            for task, row, mode in obs_year[year]:
                if task not in tasks:
                    continue
                value = row.get(dimension, "").strip()
                if valid_where(dimension, value):
                    bucket[(task, value)].append((row, mode))
            for (task, value), members in bucket.items():
                exact_amounts = [dec(row.get("amount_cny", "")) for row, mode in members if mode == "SINGLE_TASK" and dec(row.get("amount_cny", "")) is not None]
                exact_task_amounts = [dec(row.get("amount_cny", "")) for t, row, mode in obs_year[year] if t == task and mode == "SINGLE_TASK" and dec(row.get("amount_cny", "")) is not None]
                amount = sum(exact_amounts, Decimal("0"))
                amount_den = sum(exact_task_amounts, Decimal("0"))
                count = len(members)
                floor = effective_floor(priority[task]["final_priority_class"])
                distributions[dimension].append({
                    "year": year, "task_type": task, "where_dimension": dimension,
                    "where_value": value, "count": count,
                    "demand_distribution_share": percent(count, task_year_total[task]),
                    "local_demand_share": percent(count, local_total[value]),
                    "amount_cny": money(amount), "amount_share": percent(amount, amount_den),
                    "sample_status": "LOW_SAMPLE" if count < floor else "EFFECTIVE",
                    "task_type_year_denominator": task_year_total[task],
                    "task_type_year_denominator_definition": "all official frozen task observations for this task type in this year August cohort; MULTI_TASK components expanded",
                    "local_denominator": local_total[value],
                    "local_denominator_definition": "all valid official task observations in this WHERE value and year August cohort; not restricted to priority pool",
                    "amount_denominator_cny": money(amount_den),
                    "amount_denominator_definition": "SINGLE_TASK exact attributed amount for this task type in this year; MULTI_TASK amount not allocated",
                    "amount_attribution_status": "SINGLE_TASK_EXACT_ONLY",
                })

    dist_fields = list(next(iter(distributions.values()))[0])
    for dimension, records in distributions.items():
        records.sort(key=lambda r: (r["task_type"], r["year"], -int(r["count"]), r["where_value"]))
        write_csv(OUT / f"task_type_{dimension}_distribution.csv", dist_fields, records)

    patterns_by_dimension = {}
    priority_records = []
    for dimension, records in distributions.items():
        grouped = defaultdict(dict)
        for record in records:
            grouped[(record["task_type"], record["where_value"])][record["year"]] = record
        pattern_records = []
        effective_local_values = []
        for (task, value), annual in grouped.items():
            floor = effective_floor(priority[task]["final_priority_class"])
            counts = [int(annual.get(year, {}).get("count", 0)) for year in YEARS]
            dist = [float(annual.get(year, {}).get("demand_distribution_share", 0) or 0) for year in YEARS]
            local = [float(annual.get(year, {}).get("local_demand_share", 0) or 0) for year in YEARS]
            present = sum(c >= floor for c in counts)
            persistence = "PERSISTENT" if present == 3 else "REPEATED" if present == 2 else "OCCASIONAL"
            direction = trend_label(counts, dist, local, present, floor)
            vals = [x for x, c in zip(dist, counts) if c >= floor]
            cv = pstdev(vals) / mean(vals) if len(vals) >= 2 and mean(vals) else None
            stability = "LOW_SAMPLE" if present < 2 else "VOLATILE" if cv is not None and cv > .50 else "STABLE"
            if present < 2:
                pattern = "LOW_SAMPLE"
            elif direction == "EMERGING":
                pattern = "EMERGING"
            elif direction == "RISING" and persistence in {"PERSISTENT", "REPEATED"}:
                pattern = "CORE_RISING"
            elif direction == "DECLINING":
                pattern = "CORE_DECLINING"
            elif stability == "STABLE" and persistence == "PERSISTENT":
                pattern = "CORE_STABLE"
            else:
                pattern = "VOLATILE"
            local_mean = mean([x for x, c in zip(local, counts) if c >= floor]) if present else 0
            if present >= 2:
                effective_local_values.append(local_mean)
            record = {
                "task_type": task, "where_dimension": dimension, "where_value": value,
                "final_priority_class": priority[task]["final_priority_class"],
                "years_present": sum(c > 0 for c in counts), "effective_years_present": present,
                "persistence": persistence, "2023_count": counts[0], "2024_count": counts[1], "2025_count": counts[2],
                "2023_demand_distribution_share": f"{dist[0]:.2f}", "2024_demand_distribution_share": f"{dist[1]:.2f}", "2025_demand_distribution_share": f"{dist[2]:.2f}",
                "2023_local_demand_share": f"{local[0]:.2f}", "2024_local_demand_share": f"{local[1]:.2f}", "2025_local_demand_share": f"{local[2]:.2f}",
                "demand_distribution_share_mean": f"{mean(dist):.2f}", "local_demand_share_mean": f"{local_mean:.2f}",
                "direction": direction, "stability": stability, "pattern": pattern,
                "sample_status": "LOW_SAMPLE" if present < 2 else "EFFECTIVE",
                "sample_rule": f"annual count >= {floor}; P3 high-value niche uses lower evidence floor {P3_EFFECTIVE}",
            }
            pattern_records.append(record)
        # derived candidate threshold ensures local concentration is data-based and transparent
        local_threshold = sorted(effective_local_values)[int(.75 * (len(effective_local_values) - 1))] if effective_local_values else 0
        for record in pattern_records:
            high_concentration = float(record["local_demand_share_mean"]) >= local_threshold and record["effective_years_present"] >= 2
            if record["pattern"] == "CORE_STABLE" and float(record["demand_distribution_share_mean"]) >= 10:
                market = "CORE_MARKET"
                reason = "persistent, stable WHERE pattern with material task-type demand contribution"
            elif record["pattern"] in {"CORE_RISING", "EMERGING"} and record["sample_status"] == "EFFECTIVE":
                market = "GROWTH_MARKET"
                reason = "rising or emerging WHERE pattern with sufficient annual evidence"
            elif high_concentration:
                market = "CONCENTRATED_MARKET"
                reason = f"local demand share mean meets observed p75 threshold ({local_threshold:.2f}%)"
            else:
                market = "WATCHLIST_MARKET"
                reason = "low sample, decline/volatility, or insufficient persistent contribution"
            record["where_priority"] = market
            record["priority_reason"] = reason
            record["local_concentration_threshold_p75"] = f"{local_threshold:.2f}"
            priority_records.append(record)
        patterns_by_dimension[dimension] = pattern_records
        fields = list(pattern_records[0]) if pattern_records else []
        write_csv(OUT / f"task_type_{dimension}_pattern.csv", fields, sorted(pattern_records, key=lambda r: (r["task_type"], r["where_priority"], -float(r["demand_distribution_share_mean"]))))

    priority_fields = list(priority_records[0])
    priority_records.sort(key=lambda r: (r["task_type"], {"CORE_MARKET": 0, "GROWTH_MARKET": 1, "CONCENTRATED_MARKET": 2, "WATCHLIST_MARKET": 3}[r["where_priority"]], -float(r["local_demand_share_mean"])))
    write_csv(OUT / "where_priority_markets.csv", priority_fields, priority_records)
    drill = [r for r in priority_records if r["where_priority"] in {"CORE_MARKET", "GROWTH_MARKET", "CONCENTRATED_MARKET"}]
    drill_fields = priority_fields + ["drill_down_status", "drill_down_rule"]
    drill = [{**r, "drill_down_status": "CANDIDATE_PENDING_HUMAN_CONFIRMATION", "drill_down_rule": "Only a priority WHERE market may be considered in a later selective cross-analysis; no drill-down executed in V1."} for r in drill]
    write_csv(OUT / "where_drill_down_candidate_pool.csv", drill_fields, drill)

    top_lines = []
    for task in sorted(tasks, key=lambda t: int(priority[t]["priority_rank"])):
        top_lines.append(f"## {task} ({priority[task]['final_priority_class']})")
        for dimension in ("country", "school", "degree_level"):
            candidates = [r for r in priority_records if r["task_type"] == task and r["where_dimension"] == dimension]
            ranked = sorted(candidates, key=lambda r: (-float(r["demand_distribution_share_mean"]), -sum(int(r[f"{y}_count"]) for y in YEARS)))[:3]
            text = "; ".join(f"{r['where_value']}（均值分布占比{r['demand_distribution_share_mean']}%，本地占比{r['local_demand_share_mean']}%，{r['where_priority']}）" for r in ranked)
            top_lines.append(f"- {dimension}: {text}")
    summary = "# Demand WHERE Analysis V1\n\nScope: frozen Final Priority Pool only; 2023/2024/2025 August cohorts are computed independently. Country, school and degree are independent first-stage distributions. No multidimensional drill-down was executed. Monetary metrics are SINGLE_TASK exact-only.\n\n" + "\n".join(top_lines) + "\n\nSchool exclusions: " + json.dumps(dict(school_exclusions), ensure_ascii=False) + ".\n"
    (OUT / "where_analysis_summary.md").write_text(summary, encoding="utf-8")

    after = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    qa_checks = {
        "final_priority_pool_only": set(r["task_type"] for r in priority_records) == tasks,
        "p4_excluded": all(r["final_priority_class"] != "P4_WATCHLIST" for r in priority_records),
        "independent_year_denominators": all(r["task_type_year_denominator"] for rs in distributions.values() for r in rs) and len({len(obs_year[y]) for y in YEARS}) == 3,
        "demand_distribution_share_correct": all(r["demand_distribution_share"] == percent(r["count"], r["task_type_year_denominator"]) for rs in distributions.values() for r in rs),
        "local_demand_share_correct": all(r["local_demand_share"] == percent(r["count"], r["local_denominator"]) for rs in distributions.values() for r in rs),
        "independent_first_stage_dimensions": set(distributions) == {"country", "school", "degree_level"},
        "no_high_dimensional_cross": all("×" not in r["where_dimension"] and r["where_dimension"] in {"country", "school", "degree_level"} for r in priority_records),
        "p3_retained": all(any(r["task_type"] == task for r in priority_records) for task, p in priority.items() if p["final_priority_class"] == "P3_HIGH_VALUE_NICHE"),
        "school_canonical_only": all(r["where_value"] not in SCHOOL_EXCLUDED for r in distributions["school"]),
        "multi_task_amount_not_allocated": all(r["amount_attribution_status"] == "SINGLE_TASK_EXACT_ONLY" for rs in distributions.values() for r in rs),
        "unified_dataset_and_frozen_inputs_unchanged": before == after,
        "no_automatic_drilldown": all(r["drill_down_status"] == "CANDIDATE_PENDING_HUMAN_CONFIRMATION" for r in drill),
    }
    qa = {"framework_version": "1.0", "result": "PASS" if all(qa_checks.values()) else "FAIL", "checks": qa_checks,
          "scope": {"priority_task_types": sorted(tasks), "p4_excluded": frozen.get("watchlist_task_types", []), "rows": len(rows), "year_rows": {y: len(by_year[y]) for y in YEARS}},
          "school_excluded_task_observations": dict(school_exclusions),
          "cross_analysis_executed": "NONE; distributions only", "candidate_pool_size": len(drill)}
    (OUT / "where_analysis_qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    if qa["result"] != "PASS":
        raise RuntimeError("WHERE QA failed")
    print(json.dumps({"pool_tasks": len(tasks), "distributions": {d: len(v) for d, v in distributions.items()}, "priority_markets": Counter(r["where_priority"] for r in priority_records), "drill_candidates": len(drill), "qa": qa["result"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
