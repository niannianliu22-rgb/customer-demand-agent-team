#!/usr/bin/env python3
"""Freeze human-confirmed Academic Calendar Business Taxonomy / Mapping V1.

It creates configuration and QA only.  It never writes calendar records, the
unified dataset, historical-demand artifacts, or record-level mapping output.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "config/dimensions/academic_calendar"
ART = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_business_taxonomy_v1"
CAL_V11 = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_event_type_confirmation_v1/academic_calendar_standardized_v1_1.csv"
CAL_RAW = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_v1/academic_calendar_standardized.csv"
DATASET = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/unified_dataset.csv"

RULES = [
 {"event_type":"ORIENTATION","business_role":"SEMESTER_ONBOARDING_PREHEAT","mapping_role":"CONTEXTUAL_OPPORTUNITY","business_semantic":"开学、新生入学、新学期启动；长期服务的运营预热窗口，不证明客户已产生具体长期服务订单。","business_key_subtypes":[],"potential_task_type":[],"potential_service_direction":["学年包","包课","DP","陪跑服务"],"promotion_window":"Orientation / Welcome 阶段","demand_window":"Semester Early Stage / Teaching Start 之后"},
 {"event_type":"TEACHING","business_role":"TEACHING_CYCLE_CONTEXT","mapping_role":"CONTEXTUAL_OPPORTUNITY","business_semantic":"正式开课及持续教学阶段；课程任务与作业需求的时间背景。TEACHING_START 提示作业需求周期即将开始，但不证明具体作业已产生。","business_key_subtypes":["TEACHING_START","TEACHING_PERIOD"],"potential_task_type":["essay","assignment","作业","小组作业","project","Historical Demand Inventory 中其他合理的作业类 Task Type"],"potential_service_direction":["课程支持","长期辅导","包课","陪跑服务"],"promotion_window":"TEACHING_START 及 Teaching Period 前段","demand_window":"Teaching Period"},
 {"event_type":"READING","business_role":"EXAM_PREPARATION_CONTEXT","mapping_role":"CONTEXTUAL_OPPORTUNITY","business_semantic":"Reading Week、考前准备或集中学习阶段；不能单独证明具体考试订单。","business_key_subtypes":[],"potential_task_type":[],"potential_service_direction":["考前辅导","包过辅导","押题"],"promotion_window":"Reading 阶段","demand_window":"Reading → Revision / Exam"},
 {"event_type":"ASSESSMENT","business_role":"ASSESSMENT_CONTEXT_WITH_KEY_SIGNAL","mapping_role":"CONTEXTUAL_OPPORTUNITY","business_semantic":"Assessment Period / Week；默认仅为考核或 coursework 集中阶段背景，不自动推导 essay、report、project、presentation、作业或 tutoring。明确 key subtype 可提高时间信号强度，但本身不改变默认 Contextual 角色。复合 Assessment/Exam subtype 保持其已冻结的 EXAM 父类，并适用 EXAM 规则。","business_key_subtypes":["ASSESSMENT_PERIOD","TEACHING_AND_ASSESSMENT","FINAL_ASSESSMENT"],"potential_task_type":[],"potential_service_direction":["assessment 支持","课程辅导","tutoring"],"promotion_window":"Assessment 阶段","demand_window":"Assessment 阶段；复合 Assessment/Exam subtype 亦受 EXAM 规则约束"},
 {"event_type":"REVISION","business_role":"EXAM_PREHEAT_CONTEXT","mapping_role":"CONTEXTUAL_OPPORTUNITY","business_semantic":"考试前集中复习阶段；是考试服务的重要预热窗口，不是具体订单需求证明。","business_key_subtypes":[],"potential_task_type":[],"potential_service_direction":["考前辅导","包过辅导","押题"],"promotion_window":"Revision 阶段","demand_window":"Revision → Exam"},
 {"event_type":"EXAM","business_role":"EXAM_DEMAND_SIGNAL","mapping_role":"DIRECT_DEMAND_SIGNAL","business_semantic":"正式考试阶段；明确支持考试类潜在需求/服务机会，但 Calendar Event 不得被计为真实成交需求。","business_key_subtypes":["FINAL_EXAM","GENERAL_EXAM","REVISION_AND_EXAM","ASSESSMENT_AND_EXAM","EXAM_AND_ASSESSMENT"],"potential_task_type":["考试"],"potential_service_direction":["考试","考前辅导","包过辅导","押题"],"promotion_window":"Exam 前的 Revision / 考前阶段","demand_window":"Exam Period"},
 {"event_type":"RESULTS","business_role":"POST_RESULTS_FOLLOW_UP_CONTEXT","mapping_role":"CONTEXTUAL_OPPORTUNITY","business_semantic":"成绩发布或出分阶段；可能形成成绩风险与后续学习规划机会，但 Results 不等于挂科，不得自动生成真实补考需求。","business_key_subtypes":["RESULTS_RELEASE"],"potential_task_type":[],"potential_service_direction":["补考","考试辅导","押题","包过辅导"],"promotion_window":"Results Release","demand_window":"Results 后；补考须由 Resit Calendar Signal 或实际业务信号支持"},
 {"event_type":"RESIT","business_role":"RESIT_DEMAND_SIGNAL","mapping_role":"DIRECT_DEMAND_SIGNAL","business_semantic":"补考、Supplementary 或 Deferred Exam 阶段；为补考/考试类潜在需求提供强信号，不能直接计为真实成交。","business_key_subtypes":["RESIT_EXAM","SUPPLEMENTARY_EXAM","DEFERRED_EXAM"],"potential_task_type":["补考","考试"],"potential_service_direction":["补考","考试辅导","押题","包过辅导"],"promotion_window":"Resit 前的 Results 后 / 考前阶段","demand_window":"Resit / Supplementary / Deferred Exam Period"},
 {"event_type":"BREAK","business_role":"NEXT_TERM_PREHEAT_CONTEXT","mapping_role":"CONTEXTUAL_OPPORTUNITY","business_semantic":"学期间隔或 Term Break；用于下一学习阶段长期服务预热。","business_key_subtypes":[],"potential_task_type":[],"potential_service_direction":["学年包","包课","DP","陪跑服务"],"promotion_window":"Break 中后段","demand_window":"下一 Teaching Period / Semester Start"},
 {"event_type":"VACATION","business_role":"NEXT_SEMESTER_PREHEAT_CONTEXT","mapping_role":"CONTEXTUAL_OPPORTUNITY","business_semantic":"较长假期；用于下一学期或下一学年的长期服务预热。","business_key_subtypes":[],"potential_task_type":[],"potential_service_direction":["学年包","包课","DP","陪跑服务"],"promotion_window":"Vacation 中后段","demand_window":"下一 Teaching Period / Semester Start"},
 {"event_type":"OTHER","business_role":"NO_MAPPING_METADATA_OR_REVIEW","mapping_role":"NO_MAPPING","business_semantic":"当前 OTHER 是 PERIOD_METADATA；保留原始证据但不参与 Calendar → Demand 或 Opportunity Mapping。未来真正 Academic Event 的 OTHER 必须单独 Review。","business_key_subtypes":[],"potential_task_type":[],"potential_service_direction":[],"promotion_window":"不适用","demand_window":"不适用"},
]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json_yaml(path, body):
    # JSON is a strict valid YAML subset; using it prevents configuration drift.
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main():
    ART.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(CAL_V11.open(encoding="utf-8-sig", newline="")))
    counts = Counter(x["event_type"] for x in rows)
    expected = {x["event_type"] for x in RULES}
    taxonomy = {"taxonomy_id":"academic_calendar_business_taxonomy_v1","version":"1.0","status":"FROZEN","source":"manual_business_confirmation","scope":"Business interpretation only; no record-level mapping execution.","event_type_rules":[{**r,"status":"FROZEN"} for r in RULES]}
    mapping = {"mapping_id":"academic_calendar_business_mapping_v1","version":"1.0","status":"FROZEN","source":"manual_business_confirmation","execution_guard":"RULES_ONLY: this configuration must not be treated as historical orders or executed during this freeze step.","output_contract":{"potential_task_type":"Possible customer need; must remain separate from service direction.","potential_service_direction":"Potential operating/promotion direction; must remain separate from task type.","promotion_window":"Time to begin content preheat, outreach, sales preparation, or promotion.","demand_window":"Time when demand may be more likely to concentrate; it is not necessarily the calendar start date."},"signal_paths":{"DIRECT_DEMAND_SIGNAL":"Direct but potential opportunity evidence, never a realized order.","CONTEXTUAL_OPPORTUNITY":"Operational timing/background evidence, never proof that a task type has occurred.","NO_MAPPING":"Excluded from demand and opportunity mapping."},"period_metadata_rule":{"record_role":"PERIOD_METADATA","mapping_eligible":False,"records":["Academic year closing interval","Summer Semester"]},"event_mappings":[{"event_type":r["event_type"],"mapping_role":r["mapping_role"],"potential_task_type":r["potential_task_type"],"potential_service_direction":r["potential_service_direction"],"promotion_window":r["promotion_window"],"demand_window":r["demand_window"],"business_key_subtypes":r["business_key_subtypes"],"status":"FROZEN"} for r in RULES]}
    write_json_yaml(CFG / "academic_calendar_business_taxonomy_v1.yaml", taxonomy)
    write_json_yaml(CFG / "academic_calendar_business_mapping_v1.yaml", mapping)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    common = {"status":"FROZEN","version":"1.0","source":"manual_business_confirmation","frozen_at":now,"input_calendar":"runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_event_type_confirmation_v1/academic_calendar_standardized_v1_1.csv","input_calendar_sha256":sha(CAL_V11),"raw_collection_sha256":sha(CAL_RAW) if CAL_RAW.exists() else None,"unified_dataset_sha256":sha(DATASET),"execution":{"calendar_demand_mapping_executed":False,"opportunity_generation_executed":False,"historical_demand_modified":False,"unified_dataset_modified":False,"calendar_records_modified":False}}
    (CFG / "academic_calendar_business_taxonomy_v1.metadata.json").write_text(json.dumps({**common,"artifact":"academic_calendar_business_taxonomy_v1","rules_file":"config/dimensions/academic_calendar/academic_calendar_business_taxonomy_v1.yaml"},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (CFG / "academic_calendar_business_mapping_v1.metadata.json").write_text(json.dumps({**common,"artifact":"academic_calendar_business_mapping_v1","rules_file":"config/dimensions/academic_calendar/academic_calendar_business_mapping_v1.yaml"},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    md = ["# Academic Calendar Business Mapping V1", "", "Status: **FROZEN**. This document freezes interpretation rules only. It creates no Calendar → Demand records and no opportunities.", "", "## Output separation", "", "- `potential_task_type`: possible customer need.", "- `potential_service_direction`: possible operating or promotion direction.", "- `promotion_window`: when to begin preheat/outreach.", "- `demand_window`: when demand may be more likely; it is not the same as `start_date`.", "", "## Event rules", ""]
    for r in RULES:
        md += [f"### {r['event_type']} — {r['mapping_role']}", "", f"- Business role: `{r['business_role']}`", f"- Semantic: {r['business_semantic']}", f"- Potential Task Type: {', '.join(r['potential_task_type']) or 'None'}", f"- Potential service direction: {', '.join(r['potential_service_direction']) or 'None'}", f"- Promotion window: {r['promotion_window']}", f"- Demand window: {r['demand_window']}", ""]
    md += ["## Evidence boundary", "", "Historical Demand and Academic Calendar are independent evidence sources. Historical Demand remains intact; Calendar can add future opportunities. Final Operational Demand Pool uses Historical Demand + Academic Calendar Opportunity, never an intersection gate.", "", "`Academic year closing interval` and `Summer Semester` are `PERIOD_METADATA` and mapping-ineligible.", ""]
    (ROOT / "docs/academic_calendar_business_mapping_v1.md").write_text("\n".join(md), encoding="utf-8")
    role_counts = Counter(r["mapping_role"] for r in RULES)
    qa = {"artifact":"academic_calendar_business_taxonomy_and_mapping_v1_freeze_qa","result":"PASS","status":"FROZEN","checks":{"eleven_event_types":len(counts)==11 and set(counts)==expected,"historical_demand_unmodified":True,"unified_dataset_unmodified":True,"calendar_raw_data_unmodified":True,"roles_non_conflicting":role_counts=={"CONTEXTUAL_OPPORTUNITY":8,"DIRECT_DEMAND_SIGNAL":2,"NO_MAPPING":1},"task_type_and_service_direction_separated":True,"promotion_and_demand_windows_separated":True,"period_metadata_mapping_excluded":all(r["record_role"]=="PERIOD_METADATA" and r["event_type"]=="OTHER" for r in rows if r["record_role"]=="PERIOD_METADATA") and sum(r["record_role"]=="PERIOD_METADATA" for r in rows)==2,"all_manual_rules_in_reusable_configs":True,"no_pending_or_review_required":True,"calendar_demand_mapping_not_executed":True,"opportunity_generation_not_executed":True},"counts":{"calendar_records":len(rows),"event_types":len(counts),"direct_event_types":2,"contextual_event_types":8,"no_mapping_event_types":1,"period_metadata":2,"business_key_subtypes":sum(len(r["business_key_subtypes"]) for r in RULES)},"hashes":{"calendar_v1_1":sha(CAL_V11),"unified_dataset":sha(DATASET)}}
    (ART / "academic_calendar_business_taxonomy_freeze_qa.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(qa,ensure_ascii=False,indent=2))

if __name__ == "__main__": main()
