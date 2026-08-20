"""Deterministically standardize one customer-demand run without touching raw Excel.

This script consumes only run artifacts, the frozen canonical schema and the
ACTIVE business-rules registry.  It writes derived run artifacts; it never
writes under input/ or data/processed/.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import yaml
from openpyxl import Workbook, load_workbook


ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "RUN-202608-DEMAND-001"
ACTIVE_STATUSES = {"CONFIRMED", "EXCLUDED_BY_BUSINESS_RULE"}
DATE_DOT = re.compile(r"(?P<month>\d{1,2})\.(?P<day>\d{1,2})")
DATE_MONTH = re.compile(r"(?P<month>\d{1,2})月份?")
ISO_DATE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
DEGREE_MAP = {"大一": "本科", "大二": "本科", "大三": "本科", "大四": "本科", "本科": "本科", "硕士": "硕士", "博士": "博士", "高中": "高中"}


def empty(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def iso_date(value, year: int):
    """Return (standardized, transformation_kind, review_reason)."""
    if empty(value):
        return None, "blank", None
    if isinstance(value, (dt.datetime, dt.date)):
        return value.date().isoformat() if isinstance(value, dt.datetime) else value.isoformat(), "existing_date", None
    # Excel commonly stores an M.D expression such as 8.1 as a numeric cell.
    # Its displayed lexical form still fits RULE-002; values outside the M.D
    # shape (for example 0.615384...) continue to require human review.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip()
    else:
        return None, None, "date value is neither a date nor a rule-covered text pattern"
    if ISO_DATE.fullmatch(text):
        try:
            return dt.date.fromisoformat(text).isoformat(), "existing_iso_date", None
        except ValueError:
            return None, None, "invalid ISO date"
    match = DATE_DOT.search(text)
    if match:
        try:
            result = dt.date(year, int(match["month"]), int(match["day"])).isoformat()
            if "-" in text[match.end():] or "-" in text[:match.start()]:
                return result, "RULE-005_date_range_take_start", None
            if text != match.group(0):
                return result, "RULE-003_date_with_trailing_text", None
            return result, "RULE-002_month_dot_day", None
        except ValueError:
            return None, None, "invalid M.D date"
    match = DATE_MONTH.search(text)
    if match:
        try:
            return dt.date(year, int(match["month"]), 1).isoformat(), "RULE-004_month_only", None
        except ValueError:
            return None, None, "invalid month-only date"
    return None, None, "date text is not covered by RULE-002 through RULE-005"


def decimal_value(value):
    if empty(value):
        return None, None
    if isinstance(value, bool):
        return None, "boolean is not a valid amount"
    text = str(value).strip().replace(",", "").replace("¥", "").replace("￥", "")
    text = text.replace("AUD", "").replace("CNY", "").replace("RMB", "").strip()
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None, "amount is not a parseable numeric value"
    return amount, None


def row_issue(issues, source_id, source_row_id, field, original_value, reason, rule):
    issues.append({
        "issue_id": f"STD-REVIEW-{source_id}-{source_row_id}-{field}",
        "status": "STANDARDIZATION_REVIEW_REQUIRED",
        "source_id": source_id,
        "source_row_id": source_row_id,
        "field": field,
        "original_value": original_value.isoformat() if isinstance(original_value, (dt.date, dt.datetime)) else original_value,
        "reason": reason,
        "applicable_rule": rule,
        "recommended_action": "Human confirmation required; do not infer a new standardization rule."
    })


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main(run_id: str):
    run_dir = ROOT / "runs" / run_id
    artifacts = run_dir / "artifacts"
    manifest = load_json(artifacts / "source_manifest.json")
    mapping = load_json(artifacts / "schema_mapping.json")
    gate = load_json(artifacts / "schema_gate_result.json")
    schema = load_json(ROOT / "schemas" / "canonical_schema.json")
    rules = yaml.safe_load((ROOT / "config" / "data" / "standardization_rules.yaml").read_text(encoding="utf-8"))
    business_rules = (ROOT / "policies" / "business_rules.md").read_text(encoding="utf-8")

    if gate["gate_status"] != "PASS":
        raise RuntimeError("Data Standardization requires Schema Gate PASS")
    if schema["status"] != "FROZEN" or schema["schema_version"] != "1.0.0":
        raise RuntimeError("Frozen canonical schema v1.0.0 is required")
    if rules["rules_version"] != "2.0" or "Business Rules Version: 2.0" not in business_rules:
        raise RuntimeError("Business Rules v2.0 is required")
    if mapping["status"] != "COMPLETED" or manifest["status"] != "COMPLETED":
        raise RuntimeError("Intake and mapping artifacts must be COMPLETED")
    if manifest["received_source_count"] != 6 or len(manifest["sources"]) != 6:
        raise RuntimeError("Expected six received sources")

    canonical_fields = [field["name"] for field in schema["fields"]]
    canonical_set = set(canonical_fields)
    if {"amount", "deadline", "date_original", "date_standardized"} & canonical_set:
        raise RuntimeError("Canonical schema contains forbidden legacy fields")

    mapping_by_source = {}
    for item in mapping["items"]:
        if item["status"] not in ACTIVE_STATUSES:
            raise RuntimeError(f"Mapping item is not eligible for standardization: {item['id']}")
        mapping_by_source[(item["source_id"], item["raw_field_name"])] = item

    standardized_dir = artifacts / "standardized"
    standardized_dir.mkdir(parents=True, exist_ok=True)
    all_rows, source_logs, issues = [], [], []
    global_date_counts, global_degree_counts, global_currency_counts = Counter(), Counter(), Counter()
    expected_excluded = {"跟进反馈", "客户备注", "未成交原因"}

    for source in manifest["sources"]:
        if source["status"] != "RECEIVED":
            raise RuntimeError(f"Unexpected non-received source: {source['source_id']}")
        source_id, year = source["source_id"], source["year"]
        source_path = ROOT / source["file_path"]
        wb = load_workbook(source_path, read_only=True, data_only=True)
        sheet_name = wb.sheetnames[0]
        ws = wb[sheet_name]
        headers = [cell.value.strip() if isinstance(cell.value, str) else cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
        profile = load_json(artifacts / "source_profiles" / f"{source_id}.json")
        profile_fields = set(profile["sheets"][sheet_name]["fields"][idx]["field_name"] for idx in range(len(headers)))
        if set(headers) != profile_fields:
            raise RuntimeError(f"Raw headers diverge from source profile for {source_id}")

        output_rows, blank_rows, date_counts, degree_counts, currency_counts = [], 0, Counter(), Counter(), Counter()
        excluded_fields = [header for header in headers if mapping_by_source[(source_id, header)]["status"] == "EXCLUDED_BY_BUSINESS_RULE"]
        if not set(excluded_fields).issubset(expected_excluded):
            raise RuntimeError(f"Unexpected excluded field in {source_id}")

        for excel_row, values in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            raw = dict(zip(headers, values))
            if all(empty(value) for value in raw.values()):
                blank_rows += 1
                continue
            record = {field: None for field in canonical_fields}
            record.update({
                "source_id": source_id,
                "source_file": source_path.name,
                "source_sheet": sheet_name,
                "source_row_id": excel_row,
                "year": year,
                "department": source["department"],
            })
            for header, value in raw.items():
                item = mapping_by_source[(source_id, header)]
                if item["status"] == "EXCLUDED_BY_BUSINESS_RULE":
                    continue
                target = item["canonical_field"]
                if target == "consultation_date":
                    record["consultation_date_original"] = value.isoformat() if isinstance(value, (dt.date, dt.datetime)) else value
                    standardized, kind, review = iso_date(value, year)
                    record["consultation_date"] = standardized
                    date_counts[f"consultation_date:{kind or 'review_required'}"] += 1
                    if review:
                        row_issue(issues, source_id, excel_row, "consultation_date", value, review, "RULE-002~RULE-006")
                elif target == "deadline":
                    record["ddl_original"] = value.isoformat() if isinstance(value, (dt.date, dt.datetime)) else value
                    standardized, kind, review = iso_date(value, year)
                    record["ddl"] = standardized
                    date_counts[f"ddl:{kind or 'review_required'}"] += 1
                    if review:
                        row_issue(issues, source_id, excel_row, "ddl", value, review, "RULE-002~RULE-006")
                elif target == "degree_level":
                    record["degree_level_original"] = value
                    if empty(value):
                        record["degree_level"] = None
                        degree_counts["blank"] += 1
                    else:
                        normalized = DEGREE_MAP.get(str(value).strip(), "UNKNOWN")
                        record["degree_level"] = normalized
                        degree_counts[f"{str(value).strip()}->{normalized}"] += 1
                elif target == "amount":
                    amount, review = decimal_value(value)
                    if review:
                        row_issue(issues, source_id, excel_row, "amount_original", value, review, item.get("value_rule_ref"))
                        currency_counts["review_required"] += 1
                    elif amount is not None:
                        rule = item.get("value_rule_ref")
                        currency = "AUD" if rule == "RULE-009" else "CNY" if rule == "RULE-010" else None
                        if currency is None:
                            raise RuntimeError(f"Amount item lacks a currency rule: {item['id']}")
                        record["amount_original"] = float(amount)
                        record["currency_original"] = currency
                        converted = (amount * Decimal("4.5")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if currency == "AUD" else amount
                        record["amount_cny"] = float(converted)
                        currency_counts[f"{currency}_records"] += 1
                else:
                    if target not in canonical_set:
                        raise RuntimeError(f"Mapping target is not canonical: {target}")
                    record[target] = value
            output_rows.append(record)

        wb.close()
        source_csv = standardized_dir / f"{source_id}_standardized.csv"
        write_csv(source_csv, canonical_fields, output_rows)
        all_rows.extend(output_rows)
        source_logs.append({
            "source_id": source_id, "input_rows": len(list(load_workbook(source_path, read_only=True, data_only=True)[sheet_name].iter_rows(min_row=2, values_only=True))),
            "blank_rows_excluded": blank_rows, "output_rows": len(output_rows),
            "field_mappings": {"mapped_fields": len(headers) - len(excluded_fields), "excluded_fields": excluded_fields},
            "date_transformations": dict(date_counts), "degree_transformations": dict(degree_counts),
            "currency_transformations": dict(currency_counts), "excluded_fields": excluded_fields,
            "unknown_values": sum(count for key, count in degree_counts.items() if key.endswith("->UNKNOWN")),
            "review_required_values": sum(1 for issue in issues if issue["source_id"] == source_id),
            "rule_ids": ["RULE-001", "RULE-002", "RULE-003", "RULE-004", "RULE-005", "RULE-006", "RULE-007", "RULE-008", "RULE-009", "RULE-010", "RULE-011", "RULE-012"]
        })
        global_date_counts.update(date_counts); global_degree_counts.update(degree_counts); global_currency_counts.update(currency_counts)

    write_csv(artifacts / "unified_dataset.csv", canonical_fields, all_rows)
    write_xlsx(artifacts / "unified_dataset.xlsx", canonical_fields, all_rows)
    review = {"run_id": run_id, "agent": "Data Standardization Agent", "status": "HUMAN_REVIEW_REQUIRED" if issues else "COMPLETED", "review_required_count": len(issues), "issues": issues}
    write_json(artifacts / "standardization_review.json", review)
    cleaning = {
        "run_id": run_id, "agent": "Data Standardization Agent", "wave": "W3", "version": 1,
        "status": review["status"], "business_rules_version": rules["rules_version"], "canonical_schema_version": schema["schema_version"],
        "inputs": ["source_manifest.json", "source_profiles/*.json", "schema_mapping.json", "schema_gate_result.json", "canonical_schema.json", "business_rules.md", "standardization_rules.yaml"],
        "sources": source_logs,
        "totals": {"input_rows": sum(item["input_rows"] for item in source_logs), "blank_rows_excluded": sum(item["blank_rows_excluded"] for item in source_logs), "output_rows": len(all_rows), "date_transformations": dict(global_date_counts), "degree_transformations": dict(global_degree_counts), "currency_transformations": dict(global_currency_counts), "review_required_count": len(issues)},
        "excluded_fields": sorted(expected_excluded), "unified_dataset_fields": canonical_fields,
        "evidence_refs": [{"type": "manual_business_confirmation", "rule_id": f"RULE-{n:03d}"} for n in range(1, 13)]
    }
    write_json(artifacts / "cleaning_log.json", cleaning)
    standardization_rules = {"run_id": run_id, "agent": "Data Standardization Agent", "wave": "W3", "version": 1, "status": review["status"], "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "items": source_logs, "unresolved": issues, "evidence_refs": cleaning["evidence_refs"]}
    write_json(artifacts / "standardization_rules.json", standardization_rules)
    print(json.dumps({"status": review["status"], "sources": source_logs, "output_rows": len(all_rows), "review_required_count": len(issues)}, ensure_ascii=False, indent=2))


def write_csv(path: Path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader(); writer.writerows(rows)


def write_xlsx(path: Path, fields, rows):
    wb = Workbook(write_only=True); ws = wb.create_sheet("unified_dataset"); ws.append(fields)
    for row in rows: ws.append([row[field] for field in fields])
    wb.save(path)


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else RUN_ID)
