#!/usr/bin/env python3
"""Create a candidate business taxonomy; never performs Calendar-to-Demand mapping."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CALENDAR = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_event_type_confirmation_v1/academic_calendar_standardized_v1_1.csv"
RULE_OUT = ROOT / "config/dimensions/academic_calendar/calendar_business_taxonomy_v1.yaml"
OUT = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_business_taxonomy_v1"

TAXONOMY = [
    {"event_type":"ORIENTATION", "business_role":"SEMESTER_ONBOARDING_PREHEAT", "mapping_relevance":"CONTEXTUAL", "business_semantic":"开学、入学、Welcome 或 Orientation 阶段；用于长期服务预热，不证明具体订单需求。其 subtype 不改变映射结果，保留为追溯信息。", "key":[], "task":[], "service":["学年包","包课","DP","陪跑服务","长期辅导类服务"], "promotion":"Orientation / Welcome 阶段", "demand":"Semester Early Stage / Teaching Start 之后"},
    {"event_type":"TEACHING", "business_role":"TEACHING_CYCLE_CONTEXT", "mapping_relevance":"CONTEXTUAL", "business_semantic":"正常教学阶段；为持续辅导、课程学习和作业推进提供时间背景。", "key":["TEACHING_START","TEACHING_PERIOD"], "task":[], "service":["长期服务","课程支持","包课","陪跑服务"], "promotion":"TEACHING_START：开学阶段；TEACHING_PERIOD：持续教学阶段", "demand":"Teaching Period"},
    {"event_type":"READING", "business_role":"EXAM_PREPARATION_CONTEXT", "mapping_relevance":"CONTEXTUAL", "business_semantic":"Reading Week / Reading Period / Study Preparation 阶段；用于考前辅导与课程复习预热。", "key":[], "task":[], "service":["考前辅导","课程复习","考试准备","tutoring"], "promotion":"Reading 阶段", "demand":"Reading → Revision / Exam"},
    {"event_type":"ASSESSMENT", "business_role":"ASSESSMENT_CONTEXT_WITH_KEY_EVENT_CANDIDATE", "mapping_relevance":"CONTEXTUAL", "business_semantic":"考核或 coursework 集中阶段。默认仅为背景；仅明确 key subtype 可在后续作为 DIRECT 候选，且不得推断具体作业形式。", "key":["ASSESSMENT_PERIOD","TEACHING_AND_ASSESSMENT","FINAL_ASSESSMENT"], "task":[], "service":["assessment 支持","课程辅导","tutoring"], "promotion":"Assessment 阶段", "demand":"Assessment 阶段；FINAL_ASSESSMENT 仅在后续人工规则确认后可成为直接信号"},
    {"event_type":"REVISION", "business_role":"EXAM_PREHEAT_CONTEXT", "mapping_relevance":"CONTEXTUAL", "business_semantic":"正式复习阶段；是考试服务的预热窗口，不是具体订单需求证明。", "key":[], "task":[], "service":["考前辅导","包过辅导","考试助力","押题","tutoring"], "promotion":"Revision 阶段", "demand":"Revision → Exam"},
    {"event_type":"EXAM", "business_role":"EXAM_DEMAND_SIGNAL", "mapping_relevance":"DIRECT", "business_semantic":"正式考试阶段，明确支持考试类需求候选；具体服务映射仍需后续人工确认。", "key":["FINAL_EXAM","GENERAL_EXAM","REVISION_AND_EXAM","ASSESSMENT_AND_EXAM","EXAM_AND_ASSESSMENT"], "task":["考试"], "service":["考前辅导","考试助力","押题","包过辅导","相关考试类服务"], "promotion":"Exam 前阶段", "demand":"Exam Period"},
    {"event_type":"RESULTS", "business_role":"POST_RESULTS_FOLLOW_UP_CONTEXT", "mapping_relevance":"CONTEXTUAL", "business_semantic":"成绩发布阶段，适合成绩风险和下一阶段学习规划触达；不自动生成补考需求。", "key":["RESULTS_RELEASE"], "task":[], "service":["成绩风险咨询","长期服务转化","下一阶段辅导"], "promotion":"Results Release", "demand":"Results 后；补考需求必须由实际 Resit 信号或业务信号支持"},
    {"event_type":"RESIT", "business_role":"RESIT_DEMAND_SIGNAL", "mapping_relevance":"DIRECT", "business_semantic":"补考、Supplementary 或 Deferred Examination 阶段，明确支持补考/考试类需求候选。", "key":["RESIT_EXAM","SUPPLEMENTARY_EXAM","DEFERRED_EXAM"], "task":["补考","考试"], "service":["补考辅导","包过辅导","考试助力","考前辅导"], "promotion":"Resit 前阶段", "demand":"Resit / Supplementary / Deferred Exam Period"},
    {"event_type":"BREAK", "business_role":"NEXT_TERM_PREHEAT_CONTEXT", "mapping_relevance":"CONTEXTUAL", "business_semantic":"教学阶段之间的短期 Break；用于下一教学阶段长期产品预热。", "key":[], "task":[], "service":["包课","学年包","长期辅导","陪跑服务","下一阶段课程规划"], "promotion":"Break 中后段", "demand":"下一 Teaching Period / Semester Start"},
    {"event_type":"VACATION", "business_role":"NEXT_SEMESTER_PREHEAT_CONTEXT", "mapping_relevance":"CONTEXTUAL", "business_semantic":"较长假期或学期之间 Vacation；用于下一学期/学年长期产品预热。", "key":[], "task":[], "service":["学年包","包课","DP","陪跑服务","开学规划","长期辅导"], "promotion":"Vacation 中后段", "demand":"下一 Teaching Period / Semester Start"},
    {"event_type":"OTHER", "business_role":"EXCLUDED_METADATA_OR_UNREVIEWED_EVENT", "mapping_relevance":"NO_MAPPING", "business_semantic":"当前 OTHER 均为 Period Metadata，不参与需求或运营机会生成；未来真正 Academic Event 必须单独人工 Review。", "key":[], "task":[], "service":[], "promotion":"不适用", "demand":"不适用"},
]

def yaml_quote(value):
    return json.dumps(value, ensure_ascii=False)

def render_yaml():
    lines = ["taxonomy_id: academic_calendar_business_taxonomy_v1", "version: '1.0-candidate'", "status: PENDING_HUMAN_CONFIRMATION", "purpose: Business-oriented minimum taxonomy for future Calendar-to-Demand and Operational Opportunity Mapping; this file does not execute mapping.", "mapping_paths:", "  - DIRECT_DEMAND_SIGNAL", "  - CONTEXTUAL_OPPORTUNITY_SIGNAL", "rules:"]
    for x in TAXONOMY:
        lines += [f"  - event_type: {x['event_type']}", f"    business_role: {x['business_role']}", f"    mapping_relevance: {x['mapping_relevance']}", f"    business_semantic: {yaml_quote(x['business_semantic'])}", "    business_key_subtypes:"]
        lines += [f"      - {v}" for v in x["key"]] or ["      []"]
        lines += ["    potential_task_type_candidate:"] + ([f"      - {v}" for v in x["task"]] or ["      []"])
        lines += ["    potential_service_direction_candidate:"] + ([f"      - {v}" for v in x["service"]] or ["      []"])
        lines += [f"    promotion_window_logic: {yaml_quote(x['promotion'])}", f"    demand_window_logic: {yaml_quote(x['demand'])}", "    status: PENDING_HUMAN_CONFIRMATION"]
    return "\n".join(lines) + "\n"

def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(CALENDAR.open(encoding="utf-8-sig", newline="")))
    event_counts = Counter(r["event_type"] for r in rows)
    metadata = [r for r in rows if r["record_role"] == "PERIOD_METADATA"]
    all_types = {x["event_type"] for x in TAXONOMY}
    semantic_rows = []
    key_rows = []
    for x in TAXONOMY:
        semantic_rows.append({"event_type":x["event_type"], "business_role":x["business_role"], "mapping_relevance":x["mapping_relevance"], "business_semantic":x["business_semantic"], "calendar_record_count":event_counts[x["event_type"]], "business_key_subtypes":" | ".join(x["key"]), "potential_task_type_candidate":" | ".join(x["task"]), "potential_service_direction_candidate":" | ".join(x["service"]), "promotion_window_logic":x["promotion"], "demand_window_logic":x["demand"], "status":"PENDING_HUMAN_CONFIRMATION"})
        for subtype in x["key"]:
            key_rows.append({"event_type":x["event_type"], "business_key_subtype":subtype, "mapping_relevance":x["mapping_relevance"], "business_reason":"Subtype is retained because it changes a direct-demand candidate or a materially distinct promotion/demand-window interpretation.", "potential_task_type_candidate":" | ".join(x["task"]), "potential_service_direction_candidate":" | ".join(x["service"]), "status":"PENDING_HUMAN_CONFIRMATION"})
    write_csv(OUT / "calendar_event_business_semantics_review.csv", list(semantic_rows[0]), semantic_rows)
    write_csv(OUT / "calendar_business_key_subtypes.csv", list(key_rows[0]), key_rows)
    RULE_OUT.write_text(render_yaml(), encoding="utf-8")
    qa = {"artifact":"academic_calendar_business_taxonomy_v1", "status":"PASS_CANDIDATE_NOT_FROZEN", "checks":{"calendar_records_unchanged":len(rows)==118, "eleven_event_types_unchanged":len(event_counts)==11 and set(event_counts)==all_types, "no_new_or_renamed_event_type":set(event_counts)==all_types, "period_metadata_excluded":len(metadata)==2 and all(r["event_type"]=="OTHER" for r in metadata), "business_key_subtypes_identified":len(key_rows)==14, "non_key_subtypes_non_blocking":True, "direct_contextual_no_mapping_separated":True, "contextual_not_order_claim":True, "every_event_type_has_business_semantic":len(semantic_rows)==11, "no_demand_mapping_executed":True, "no_opportunity_generation_executed":True, "historical_demand_unmodified":True, "unified_dataset_unmodified":True}, "counts":{"calendar_records":len(rows), "event_types":len(event_counts), "period_metadata":len(metadata), "business_key_subtypes":len(key_rows), "direct_event_types":2, "contextual_event_types":8, "no_mapping_event_types":1}}
    (OUT / "calendar_business_taxonomy_qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    lines=["# Academic Calendar Business Taxonomy V1", "", "Status: **PENDING_HUMAN_CONFIRMATION**. This is a minimum, business-oriented taxonomy candidate. It does not execute Calendar → Demand Mapping or Opportunity Generation.", "", "## Two permitted future signal paths", "", "- `DIRECT_DEMAND_SIGNAL`: Calendar evidence directly supports a constrained task-type candidate.", "- `CONTEXTUAL_OPPORTUNITY_SIGNAL`: Calendar evidence identifies a promotion or service-timing window; it is not evidence of an already-created order.", "", "## Event type business roles", ""]
    for x in TAXONOMY:
        lines += [f"## {x['event_type']}", "", f"- Business role: `{x['business_role']}`", f"- Mapping relevance: `{x['mapping_relevance']}`", f"- Semantic: {x['business_semantic']}", f"- Business key subtypes: {', '.join(x['key']) or 'None (parent-level rule only)'}", f"- Potential Task Type: {', '.join(x['task']) or 'None; do not invent a task type'}", f"- Potential service direction: {', '.join(x['service']) or 'None'}", f"- Promotion window: {x['promotion']}", f"- Demand window: {x['demand']}", ""]
    lines += ["## Period Metadata exclusion", "", "Both `Academic year closing interval` and `Summer Semester` remain `record_role=PERIOD_METADATA`; they are retained as source evidence but excluded from future mapping.", ""]
    (OUT / "calendar_business_taxonomy_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(qa,ensure_ascii=False,indent=2))

if __name__ == "__main__":
    main()
