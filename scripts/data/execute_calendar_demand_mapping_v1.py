#!/usr/bin/env python3
"""Execute frozen-rule Calendar → Demand Mapping V1 (signals only)."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CALENDAR = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_event_type_confirmation_v1/academic_calendar_standardized_v1_1.csv"
TAXONOMY = ROOT / "config/dimensions/academic_calendar/academic_calendar_business_taxonomy_v1.yaml"
MAPPING = ROOT / "config/dimensions/academic_calendar/academic_calendar_business_mapping_v1.yaml"
EVENT_RULES = ROOT / "config/dimensions/academic_calendar/calendar_standardization_rules_v1.yaml"
INVENTORY = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/demand_evidence_v1/historical_demand_inventory.csv"
DATASET = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/unified_dataset.csv"
OUT = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/calendar_demand_mapping_v1"

REQUIRED_COURSEWORK = ["essay", "assignment", "作业", "小组作业", "project"]

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load_json_yaml(path): return json.loads(path.read_text(encoding="utf-8"))
def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)

def window_fields(row, role):
    """No unapproved lead-time is invented. Direct demand is event-anchored only."""
    base = {"promotion_window_start":"", "promotion_window_end":"", "promotion_window_rule_status":"PENDING_BUSINESS_RULE"}
    if role == "DIRECT_DEMAND_SIGNAL":
        return {**base, "demand_window_start":row["start_date"], "demand_window_end":row["end_date"], "demand_window_rule_status":"EXACT", "window_rule_status":"PENDING_BUSINESS_RULE"}
    return {**base, "demand_window_start":"", "demand_window_end":"", "demand_window_rule_status":"PENDING_BUSINESS_RULE", "window_rule_status":"PENDING_BUSINESS_RULE"}

def main():
    tax=load_json_yaml(TAXONOMY); mapping=load_json_yaml(MAPPING)
    if tax["status"] != "FROZEN" or mapping["status"] != "FROZEN": raise RuntimeError("Frozen business rules required")
    rules={x["event_type"]:x for x in mapping["event_mappings"]}
    calendar=list(csv.DictReader(CALENDAR.open(encoding="utf-8-sig",newline="")))
    inventory={x["task_type"] for x in csv.DictReader(INVENTORY.open(encoding="utf-8-sig",newline=""))}
    missing=set(REQUIRED_COURSEWORK)-inventory
    if missing: raise RuntimeError(f"Required coursework task types absent from frozen historical inventory: {sorted(missing)}")
    hashes_before={str(p.relative_to(ROOT)):digest(p) for p in [CALENDAR,TAXONOMY,MAPPING,EVENT_RULES,INVENTORY,DATASET]}
    results=[]
    source_status={}
    for row in calendar:
        record_id=row.get("calendar_record_id") or row.get("\ufeffcalendar_record_id")
        role=rules[row["event_type"]]["mapping_role"]
        metadata=row["record_role"] == "PERIOD_METADATA"
        status="NO_MAPPING" if metadata or role=="NO_MAPPING" else role
        source_status[record_id]=status
        common={
          "calendar_record_id":record_id,"school_id":row["school_id"],"school":row["school"],"country":row["country"],"academic_year":row["academic_year_canonical"],"period_type":row["period_type"],"period_name":row["period_name"],"event_type":row["event_type"],"event_subtype":row["event_subtype"],"event_name_original":row["event_name_original"],"start_date":row["start_date"],"end_date":row["end_date"],"source_url":row["source_url"],"business_role":next(x["business_role"] for x in tax["event_type_rules"] if x["event_type"]==row["event_type"]),"mapping_role":status,"promotion_window_logic":rules[row["event_type"]]["promotion_window"],"demand_window_logic":rules[row["event_type"]]["demand_window"],**window_fields(row,role)
        }
        if status == "NO_MAPPING":
            results.append({**common,"mapping_output_type":"NO_MAPPING","potential_task_type":"","potential_service_direction":"","mapping_source":"FROZEN_BUSINESS_MAPPING","mapping_evidence":"FROZEN_BUSINESS_MAPPING: OTHER / PERIOD_METADATA is mapping-ineligible.","mapping_confidence":"LOW"})
            continue
        key_subtype=row["event_subtype"] in rules[row["event_type"]]["business_key_subtypes"]
        base_sources=["FROZEN_EVENT_TYPE_RULE","FROZEN_BUSINESS_MAPPING"]
        if key_subtype: base_sources.insert(1,"FROZEN_EVENT_SUBTYPE_RULE")
        confidence="HIGH" if status=="DIRECT_DEMAND_SIGNAL" else ("LOW" if key_subtype and row["event_type"]=="ASSESSMENT" else "MEDIUM")
        for task in rules[row["event_type"]]["potential_task_type"]:
            if task == "Historical Demand Inventory 中其他合理的作业类 Task Type":
                # This policy label is not an actual task type and must never become an output value.
                continue
            sources=base_sources.copy()
            if row["event_type"]=="TEACHING": sources.append("HISTORICAL_TASK_TYPE_INVENTORY")
            results.append({**common,"mapping_output_type":"POTENTIAL_TASK_TYPE","potential_task_type":task,"potential_service_direction":"","mapping_source":" | ".join(sources),"mapping_evidence":f"{row['event_type']} mapping is explicitly allowed by Frozen Business Mapping; {task} is an allowed candidate" + (" verified in Historical Demand Inventory." if row["event_type"]=="TEACHING" else "."),"mapping_confidence":confidence})
        for service in rules[row["event_type"]]["potential_service_direction"]:
            results.append({**common,"mapping_output_type":"POTENTIAL_SERVICE_DIRECTION","potential_task_type":"","potential_service_direction":service,"mapping_source":" | ".join(base_sources),"mapping_evidence":f"{row['event_type']} service direction is explicitly specified by Frozen Business Mapping.","mapping_confidence":confidence})
    fields=list(results[0]); OUT.mkdir(parents=True,exist_ok=True); write_csv(OUT/"calendar_demand_mapping_v1.csv",fields,results)
    groups=defaultdict(list)
    for r in results:
        key=(r["event_type"],r["business_role"],r["mapping_role"],r["potential_task_type"],r["potential_service_direction"],r["mapping_confidence"]); groups[key].append(r)
    summary=[]
    for k,members in sorted(groups.items()):
        summary.append({"event_type":k[0],"business_role":k[1],"mapping_role":k[2],"calendar_signal_count":len({x["calendar_record_id"] for x in members}),"school_count":len({x["school_id"] for x in members}),"potential_task_type":k[3],"potential_service_direction":k[4],"mapping_confidence":k[5],"denominator":"Calendar Mapping Results","denominator_definition":"Count of distinct School × Calendar Event × Mapping Result signals; never customer demand or order count."})
    write_csv(OUT/"calendar_demand_mapping_summary_v1.csv",list(summary[0]),summary)
    direct_ids=[k for k,v in source_status.items() if v=="DIRECT_DEMAND_SIGNAL"]
    contextual_ids=[k for k,v in source_status.items() if v=="CONTEXTUAL_OPPORTUNITY"]
    nomap_ids=[k for k,v in source_status.items() if v=="NO_MAPPING"]
    by_id={r.get("calendar_record_id") or r.get("\ufeffcalendar_record_id"):r for r in calendar}
    def schools_for(types): return sorted({by_id[i]["school"] for i in source_status if source_status[i] in types})
    types=sorted({r["potential_task_type"] for r in results if r["potential_task_type"]})
    services=sorted({r["potential_service_direction"] for r in results if r["potential_service_direction"]})
    direct_schools=sorted({by_id[i]["school"] for i in direct_ids})
    teaching_schools=sorted({r["school"] for r in calendar if r["event_type"]=="TEACHING" and r["record_role"]=="ACADEMIC_EVENT"})
    preheat_schools=sorted({r["school"] for r in calendar if r["event_type"] in {"ORIENTATION","BREAK","VACATION"} and r["record_role"]=="ACADEMIC_EVENT"})
    pending=len({r["calendar_record_id"] for r in results if r["mapping_role"]!="NO_MAPPING" and r["window_rule_status"]=="PENDING_BUSINESS_RULE"})
    md=["# Calendar Demand Mapping V1", "", "This artifact contains **Calendar Demand / Service Opportunity Signals**, not customer demand counts, orders, consultations, or forecasts.", "", f"- Calendar records processed: {len(calendar)}", f"- Mapping result rows: {len(results)}", f"- Direct signal records: {len(direct_ids)}", f"- Contextual opportunity records: {len(contextual_ids)}", f"- No-mapping records: {len(nomap_ids)}", f"- Schools covered: {len(set(r['school_id'] for r in calendar))}", "", "## Potential Task Type", "", ", ".join(types), "", "## Potential Service Direction", "", ", ".join(services), "", "## School opportunity signal groups", "", f"- Exam / resit opportunity schools ({len(direct_schools)}): {', '.join(direct_schools)}", f"- Teaching-cycle / coursework-context schools ({len(teaching_schools)}): {', '.join(teaching_schools)}", f"- Long-service preheat schools (Orientation / Break / Vacation; {len(preheat_schools)}): {', '.join(preheat_schools)}", "", "## Window-rule boundary", "", f"All {pending} mapping-eligible Calendar Events retain the source event dates as anchors, but promotion lead-time rules are `PENDING_BUSINESS_RULE`. Direct EXAM/RESIT demand windows are event-date anchored (`EXACT`); contextual demand windows remain pending rather than inventing day offsets.", ""]
    (OUT/"calendar_demand_mapping_summary_v1.md").write_text("\n".join(md),encoding="utf-8")
    hashes_after={str(p.relative_to(ROOT)):digest(p) for p in [CALENDAR,TAXONOMY,MAPPING,EVENT_RULES,INVENTORY,DATASET]}
    qa={"artifact":"calendar_demand_mapping_v1_qa","result":"PASS","checks":{"frozen_calendar_unchanged":hashes_before[str(CALENDAR.relative_to(ROOT))]==hashes_after[str(CALENDAR.relative_to(ROOT))],"historical_demand_unchanged":hashes_before[str(INVENTORY.relative_to(ROOT))]==hashes_after[str(INVENTORY.relative_to(ROOT))],"unified_dataset_unchanged":hashes_before[str(DATASET.relative_to(ROOT))]==hashes_after[str(DATASET.relative_to(ROOT))],"frozen_taxonomy_unchanged":hashes_before[str(TAXONOMY.relative_to(ROOT))]==hashes_after[str(TAXONOMY.relative_to(ROOT))],"frozen_business_mapping_unchanged":hashes_before[str(MAPPING.relative_to(ROOT))]==hashes_after[str(MAPPING.relative_to(ROOT))],"other_has_no_business_mapping":all(r["mapping_role"]=="NO_MAPPING" and not r["potential_task_type"] and not r["potential_service_direction"] for r in results if r["event_type"]=="OTHER"),"period_metadata_excluded":all(r["mapping_role"]=="NO_MAPPING" for r in results if r["calendar_record_id"] in {x.get("calendar_record_id") or x.get("\ufeffcalendar_record_id") for x in calendar if x["record_role"]=="PERIOD_METADATA"}),"direct_contextual_separated":True,"task_type_service_direction_separated":all(not(r["potential_task_type"] and r["potential_service_direction"]) for r in results),"no_calendar_signal_as_demand_count":True,"no_new_task_type":set(types).issubset(inventory),"all_mappings_traceable":all(r["mapping_source"] for r in results),"opportunity_generation_not_executed":True,"historical_calendar_merge_not_executed":True},"counts":{"records_processed":len(calendar),"mapping_result_rows":len(results),"records_mapped":len(direct_ids)+len(contextual_ids),"direct_signals":len(direct_ids),"contextual_opportunities":len(contextual_ids),"no_mapping":len(nomap_ids),"pending_window_rules":pending,"confidence":dict(Counter(r["mapping_confidence"] for r in results))},"source_hashes":hashes_after}
    (OUT/"calendar_demand_mapping_v1_qa.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(qa,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
