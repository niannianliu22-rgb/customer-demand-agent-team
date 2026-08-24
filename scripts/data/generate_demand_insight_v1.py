#!/usr/bin/env python3
"""Read-only Demand Insight V1 analysis based on the standardized unified dataset."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "runs/RUN-202608-DEMAND-001"
ART = RUN / "artifacts"
DATA = ART / "unified_dataset.csv"
OUT = ART / "demand_insight_v1"
LOW_SAMPLE = 5


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def safe_amount(value):
    try:
        return Decimal(value) if value.strip() else None
    except (InvalidOperation, AttributeError):
        return None


def amount_stats(rows):
    values = [safe_amount(row.get("amount_cny", "")) for row in rows]
    values = sorted(value for value in values if value is not None)
    total = sum(values, Decimal("0"))
    return {"record_count": len(rows), "amount_observed_records": len(values), "amount_cny_sum": format(total.quantize(Decimal("0.01")), "f"), "amount_cny_mean": format((total / len(values)).quantize(Decimal("0.01")), "f") if values else "", "amount_cny_median": format(median(values).quantize(Decimal("0.01")), "f") if values else "", "amount_cny_max": format(values[-1].quantize(Decimal("0.01")), "f") if values else ""}


def sample_flag(count):
    return "LOW_SAMPLE" if count < LOW_SAMPLE else ""


def group_rows(rows, key):
    result = defaultdict(list)
    for row in rows: result[key(row)].append(row)
    return result


def distribution(rows, key_name, key, extra=None):
    grouped = group_rows(rows, key)
    output = []
    for value, bucket in sorted(grouped.items(), key=lambda item: (-len(item[1]), str(item[0]))):
        row = {key_name: value, **amount_stats(bucket), "sample_flag": sample_flag(len(bucket))}
        if extra: row.update(extra(value, bucket))
        output.append(row)
    return output


def parse_month(value):
    try: return datetime.fromisoformat(value).strftime("%Y-%m")
    except (ValueError, TypeError): return "UNPARSEABLE_OR_BLANK"


def task_demands(rows):
    demands = []
    excluded = unknown = multi_records = 0
    for row in rows:
        status = row.get("task_type_standardization_status", "")
        if status == "EXCLUDED_BY_BUSINESS_RULE": excluded += 1; continue
        if status in {"UNKNOWN", "UNMATCHED", "REVIEW_REQUIRED"}: unknown += 1; continue
        if row.get("task_type_mode") == "MULTI_TASK":
            multi_records += 1
            try: components = json.loads(row["task_type_components"])
            except (json.JSONDecodeError, TypeError): components = []
            for component in components:
                demands.append((component, row, "MULTI_COMPONENT"))
        elif status == "STANDARDIZED": demands.append((row["task_type"], row, "SINGLE_TASK"))
    return demands, {"excluded_task_type_records": excluded, "unknown_or_unmatched_task_type_records": unknown, "multi_task_records": multi_records, "expanded_task_type_observations": len(demands), "method": "SINGLE_TASK counts once by official task_type; MULTI_TASK counts once for every frozen component; EXCLUDED is omitted; UNKNOWN/UNMATCHED/REVIEW_REQUIRED omitted from official ranking."}


def matrix(rows, row_key, col_key, path, row_label, col_label):
    grouped = Counter((row_key(row), col_key(row)) for row in rows)
    output = [{row_label: left, col_label: right, "record_count": count, "sample_flag": sample_flag(count)} for (left, right), count in sorted(grouped.items(), key=lambda item: (-item[1], item[0]))]
    write_csv(path, [row_label, col_label, "record_count", "sample_flag"], output)
    return output


def main():
    before_digest = hashlib.sha256(DATA.read_bytes()).hexdigest()
    rows = read_csv(DATA)
    if len(rows) != 818: raise RuntimeError(f"expected 818 rows, got {len(rows)}")
    OUT.mkdir(parents=True, exist_ok=True)
    special_school = {"", "UNKNOWN", "UNSTANDARDIZED", "NON_SCHOOL", "NON_UNIVERSITY_ENTITY", "UNRESOLVED"}
    valid_school_rows = [row for row in rows if row.get("school", "") not in special_school]
    school_rows = distribution(valid_school_rows, "school", lambda row: row["school"], lambda value, bucket: {"school_status": "CANONICAL_OR_RETAINED_VALUE"})
    write_csv(OUT / "school_demand.csv", ["school", "school_status", "record_count", "amount_observed_records", "amount_cny_sum", "amount_cny_mean", "amount_cny_median", "amount_cny_max", "sample_flag"], school_rows)
    task_entries, task_method = task_demands(rows)
    task_group = defaultdict(list)
    task_modes = defaultdict(Counter)
    for task, row, mode in task_entries: task_group[task].append(row); task_modes[task][mode] += 1
    task_rows = []
    for task, bucket in sorted(task_group.items(), key=lambda item: (-len(item[1]), item[0])):
        task_rows.append({"task_type": task, **amount_stats(bucket), "single_task_observations": task_modes[task]["SINGLE_TASK"], "multi_component_observations": task_modes[task]["MULTI_COMPONENT"], "sample_flag": sample_flag(len(bucket))})
    write_csv(OUT / "task_type_demand.csv", ["task_type", "record_count", "single_task_observations", "multi_component_observations", "amount_observed_records", "amount_cny_sum", "amount_cny_mean", "amount_cny_median", "amount_cny_max", "sample_flag"], task_rows)
    def channel_key(row):
        return row["channel"] if row["channel"] else ""
    channel_rows = distribution(rows, "channel", channel_key, lambda value, bucket: {"channel_group": bucket[0]["channel_group"], "channel_status": "LEGAL_NULL_SECONDARY" if value == "" else "CANONICAL"})
    write_csv(OUT / "channel_demand.csv", ["channel_group", "channel", "channel_status", "record_count", "amount_observed_records", "amount_cny_sum", "amount_cny_mean", "amount_cny_median", "amount_cny_max", "sample_flag"], channel_rows)
    monthly_rows = distribution(rows, "month", lambda row: parse_month(row.get("consultation_date", "")), lambda value, bucket: {"parsed_date_status": "PARSED" if value != "UNPARSEABLE_OR_BLANK" else "UNPARSEABLE_OR_BLANK"})
    write_csv(OUT / "monthly_demand_trend.csv", ["month", "parsed_date_status", "record_count", "amount_observed_records", "amount_cny_sum", "amount_cny_mean", "amount_cny_median", "amount_cny_max", "sample_flag"], monthly_rows)
    country_rows = distribution(rows, "country", lambda row: row.get("country", "") or "(空值)")
    degree_rows = distribution(rows, "degree_level", lambda row: row.get("degree_level", "") or "(空值)")
    department_rows = distribution(rows, "department", lambda row: row["department"])
    write_csv(OUT / "country_demand.csv", ["country", "record_count", "amount_observed_records", "amount_cny_sum", "amount_cny_mean", "amount_cny_median", "amount_cny_max", "sample_flag"], country_rows)
    write_csv(OUT / "degree_demand.csv", ["degree_level", "record_count", "amount_observed_records", "amount_cny_sum", "amount_cny_mean", "amount_cny_median", "amount_cny_max", "sample_flag"], degree_rows)
    write_csv(OUT / "department_demand.csv", ["department", "record_count", "amount_observed_records", "amount_cny_sum", "amount_cny_mean", "amount_cny_median", "amount_cny_max", "sample_flag"], department_rows)
    # Cross analyses use individual official task observations, so MULTI_TASK may appear in several cells.
    cross_task_rows = [{**row, "_task": task} for task, row, _ in task_entries]
    school_task = matrix([row for row in cross_task_rows if row.get("school", "") not in special_school], lambda row: row["school"], lambda row: row["_task"], OUT / "school_task_type_matrix.csv", "school", "task_type")
    degree_task = matrix(cross_task_rows, lambda row: row.get("degree_level", "") or "(空值)", lambda row: row["_task"], OUT / "degree_task_type_matrix.csv", "degree_level", "task_type")
    channel_task = matrix(cross_task_rows, lambda row: row["channel"] if row["channel"] else "", lambda row: row["_task"], OUT / "channel_task_type_matrix.csv", "channel", "task_type")
    school_month = matrix([row for row in valid_school_rows], lambda row: row["school"], lambda row: parse_month(row.get("consultation_date", "")), OUT / "school_month_trend.csv", "school", "month")
    task_month = Counter((task, parse_month(row.get("consultation_date", ""))) for task, row, _ in task_entries)
    write_csv(OUT / "task_type_month_trend.csv", ["task_type", "month", "demand_observations", "sample_flag"], [{"task_type": task, "month": month, "demand_observations": count, "sample_flag": sample_flag(count)} for (task, month), count in sorted(task_month.items(), key=lambda item: (-item[1], item[0]))])
    ddl_rows = distribution(rows, "ddl_month", lambda row: parse_month(row.get("ddl", "")), lambda value, bucket: {"ddl_status": "PARSED" if value != "UNPARSEABLE_OR_BLANK" else "UNPARSEABLE_OR_BLANK"})
    write_csv(OUT / "ddl_demand_distribution.csv", ["ddl_month", "ddl_status", "record_count", "amount_observed_records", "amount_cny_sum", "amount_cny_mean", "amount_cny_median", "amount_cny_max", "sample_flag"], ddl_rows)
    total_amount = amount_stats(rows)
    top_school_task = school_task[0] if school_task else {}
    overview = {
        "run_id": RUN.name, "analysis": "Demand Insight V1", "input": str(DATA.relative_to(ROOT)), "input_sha256": before_digest,
        "total_records": len(rows), "analysis_scope": {"school_ranking_population": len(valid_school_rows), "school_nonranked_records": len(rows) - len(valid_school_rows), "task_type_method": task_method, "channel_null_secondary_definition": "Empty channel is a legal secondary-channel null only for channel_original=新客户 and channel_group=新客户; it is not assigned to a named channel."},
        "amount_distribution": total_amount, "top_10_schools": school_rows[:10], "top_10_task_types": task_rows[:10], "top_channels": channel_rows[:10], "top_school_task_type_combination": top_school_task,
        "monthly_trend": monthly_rows, "ddl_distribution": ddl_rows, "department_difference": department_rows,
        "data_limitations": [
            "All source files are August extracts across different years; cross-calendar-month seasonality cannot be inferred from this run alone.",
            "Rows with non-canonical/non-ranked school states are excluded from Top-school ranking and are retained only in the overall sample.",
            "Task_type MULTI_TASK is expanded by frozen components; component observations are not mutually exclusive and may exceed record count.",
            "Rows with legal null secondary channel are included in channel_group=新客户 but excluded from named-channel attribution.",
            "LOW_SAMPLE marks any grouped result with fewer than 5 observations."
        ]
    }
    (OUT / "demand_overview.json").write_text(json.dumps(overview, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = f"""# Demand Insight V1 Summary

## Scope

- Input: `{DATA.relative_to(ROOT)}`; read-only analysis of {len(rows)} standardized records.
- Task type: {task_method['method']}
- Legal empty secondary channels: {sum(1 for row in rows if not row['channel'])}; they remain in `channel_group=新客户` and are excluded from named-channel attribution.

## Leading demand signals

- Top school: {school_rows[0]['school'] if school_rows else 'N/A'} ({school_rows[0]['record_count'] if school_rows else 0} records).
- Top task type: {task_rows[0]['task_type'] if task_rows else 'N/A'} ({task_rows[0]['record_count'] if task_rows else 0} task observations).
- Top school × task_type: {top_school_task.get('school', 'N/A')} × {top_school_task.get('task_type', 'N/A')} ({top_school_task.get('record_count', 0)} observations).
- Customer structure: 老客户 {sum(1 for row in rows if row['channel_group']=='老客户')} / 新客户 {sum(1 for row in rows if row['channel_group']=='新客户')}.

## Interpretation limits

{chr(10).join('- ' + item for item in overview['data_limitations'])}
"""
    (OUT / "demand_insight_summary.md").write_text(summary, encoding="utf-8")
    if hashlib.sha256(DATA.read_bytes()).hexdigest() != before_digest: raise RuntimeError("analysis must not modify unified_dataset.csv")
    print(json.dumps({"total_records": len(rows), "top_school": school_rows[0]['school'] if school_rows else None, "top_task_type": task_rows[0]['task_type'] if task_rows else None, "artifacts": str(OUT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
