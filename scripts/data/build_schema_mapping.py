"""
build_schema_mapping.py — Schema Mapping Agent's mapping-assembly driver for
a specific run.

Required Shared Rules (read every run, per agents/schema_mapping.md):
  - policies/business_rules.md               (human-readable source of truth)
  - config/data/standardization_rules.yaml   (machine-readable; this script
                                               parses THIS file programmatically)

Reads real Data Intake Agent artifacts (source_manifest.json + per-source
profiles) plus the shared rules registry above, applies a hand-authored
raw-field -> canonical-field semantic table (this IS the Agent's semantic
judgment, analogous to Critic's business reasoning — not a "computation"),
cross-checks it against each source's ACTUAL profiled columns (never invents
a field that isn't really there), and writes schema_mapping.json.

Fields covered by an ACTIVE manual_business_confirmation rule (RULE-007..012)
are always CONFIRMED or EXCLUDED_BY_BUSINESS_RULE as the rule dictates —
human-confirmed rules outrank this Agent's own inference (see
docs/AGENT_CONTRACT.md section 11), so those fields must never be downgraded
to REVIEW_REQUIRED.

No value-level processing happens here (no date parsing, no currency
conversion, no row filtering) — only field-name -> canonical-field mapping
decisions (plus, where a rule specifies it, which output fields and which
value-level rule Data Standardization Agent must apply), per Schema Mapping
Agent's contract boundary (agents/schema_mapping.md).
"""

import datetime
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RULE_IDS_BACKING_MAPPINGS = {"RULE-007", "RULE-008", "RULE-009", "RULE-010", "RULE-011", "RULE-012"}
VALID_STATUSES = {"CONFIRMED", "REVIEW_REQUIRED", "UNMAPPED", "EXCLUDED_BY_BUSINESS_RULE"}

RULE_007 = {"type": "manual_business_confirmation", "rule_id": "RULE-007"}
RULE_008 = {"type": "manual_business_confirmation", "rule_id": "RULE-008"}
RULE_009 = {"type": "manual_business_confirmation", "rule_id": "RULE-009"}
RULE_010 = {"type": "manual_business_confirmation", "rule_id": "RULE-010"}
RULE_011 = {"type": "manual_business_confirmation", "rule_id": "RULE-011"}
RULE_012 = {"type": "manual_business_confirmation", "rule_id": "RULE-012"}

AMOUNT_OUTPUT_FIELDS = ["amount_original", "currency_original", "amount_cny"]
DEGREE_OUTPUT_FIELDS = ["degree_level_original", "degree_level"]

# Raw field name -> mapping decision dict:
#   canonical_field, status, rationale, rule_evidence (or None),
#   output_fields (optional), value_rule_ref (optional)
MAPPING_TABLE = {
    "日期": dict(canonical_field="consultation_date", status="CONFIRMED",
                rationale="字段名与全部 6 个 source 中的用法一致，均为记录的主日期字段；值本身格式不一"
                          "（datetime/数值/文本），值级标准化属于 Data Standardization Agent 依据 "
                          "RULE-002～005 处理的范围，本阶段只做字段名映射。",
                rule_evidence=None),
    "国家": dict(canonical_field="country", status="CONFIRMED",
                rationale="字段名清晰、全部出现场景语义一致（意向留学国家）。", rule_evidence=None),
    "学校": dict(canonical_field="school", status="CONFIRMED",
                rationale="与「院校」为同义变体，均指意向学校/院校名称，语义无歧义。", rule_evidence=None),
    "院校": dict(canonical_field="school", status="CONFIRMED",
                rationale="与「学校」为同义变体，均指意向学校/院校名称，语义无歧义。", rule_evidence=None),
    "学历": dict(canonical_field="degree_level", status="CONFIRMED",
                rationale="人工确认业务规则 RULE-012：学历字段映射为 degree_level，"
                          "大一/大二/大三/大四归一为「本科」，其余明确学历原样映射，无法判断的取值为 UNKNOWN。"
                          "字段级映射本身无歧义，值级归一由 Data Standardization Agent 执行。",
                rule_evidence=RULE_012, output_fields=DEGREE_OUTPUT_FIELDS, value_rule_ref="RULE-012"),
    "专业/课程": dict(canonical_field="major", status="CONFIRMED",
                    rationale="与「专业」为同义变体，均指专业/课程方向，语义无歧义。", rule_evidence=None),
    "专业": dict(canonical_field="major", status="CONFIRMED",
                rationale="与「专业/课程」为同义变体，均指专业/课程方向，语义无歧义。", rule_evidence=None),
    "DDL": dict(canonical_field="deadline", status="CONFIRMED",
                rationale="字段名为业务通用缩写（deadline），全部出现场景语义一致；值级标准化同样属于 "
                          "Data Standardization Agent 范围。", rule_evidence=None),
    "作业形式": dict(canonical_field="task_type", status="CONFIRMED",
                   rationale="人工确认业务规则 RULE-008：作业形式/作业类型/咨询内容 统一映射为 task_type"
                             "（仅字段级，值级未确认）。", rule_evidence=RULE_008),
    "作业类型": dict(canonical_field="task_type", status="CONFIRMED",
                   rationale="人工确认业务规则 RULE-008：作业形式/作业类型/咨询内容 统一映射为 task_type"
                             "（仅字段级，值级未确认）。", rule_evidence=RULE_008),
    "咨询内容": dict(canonical_field="task_type", status="CONFIRMED",
                   rationale="人工确认业务规则 RULE-008：作业形式/作业类型/咨询内容 统一映射为 task_type"
                             "（仅字段级，值级未确认）。", rule_evidence=RULE_008),
    "客户来源": dict(canonical_field="channel", status="CONFIRMED",
                   rationale="人工确认业务规则 RULE-007：客户来源/客户类型 统一映射为 channel。",
                   rule_evidence=RULE_007),
    "客户类型": dict(canonical_field="channel", status="CONFIRMED",
                   rationale="人工确认业务规则 RULE-007：客户来源/客户类型 统一映射为 channel。",
                   rule_evidence=RULE_007),
    "订单编号": dict(canonical_field="order_id", status="CONFIRMED",
                   rationale="字段名清晰，语义无歧义（订单/记录唯一编号）。", rule_evidence=None),
    "订单金额/澳刀": dict(canonical_field="amount", status="CONFIRMED",
                      rationale="人工确认业务规则 RULE-009：该字段记录实际澳币（AUD）收款金额，标准化为 "
                                "amount_original/currency_original=AUD/amount_cny（固定汇率 4.5，禁止调用"
                                "实时汇率）。此前因跨 source 币种标注不一致被标记 REVIEW_REQUIRED，"
                                "RULE-009 已解决该口径分歧。",
                      rule_evidence=RULE_009, output_fields=AMOUNT_OUTPUT_FIELDS, value_rule_ref="RULE-009"),
    "订单金额/人民币": dict(canonical_field="amount", status="CONFIRMED",
                       rationale="人工确认业务规则 RULE-010：该字段记录人民币（CNY）金额，标准化为 "
                                 "amount_original/currency_original=CNY/amount_cny（无需换算）。"
                                 "此前因跨 source 币种标注不一致被标记 REVIEW_REQUIRED，RULE-010 已解决该口径分歧。",
                       rule_evidence=RULE_010, output_fields=AMOUNT_OUTPUT_FIELDS, value_rule_ref="RULE-010"),
    "金额": dict(canonical_field="amount", status="CONFIRMED",
                rationale="人工确认业务规则 RULE-010：该字段记录人民币（CNY）金额，标准化为 "
                          "amount_original/currency_original=CNY/amount_cny（无需换算）。"
                          "此前因未标注币种被标记 REVIEW_REQUIRED，RULE-010 已解决该口径分歧。",
                rule_evidence=RULE_010, output_fields=AMOUNT_OUTPUT_FIELDS, value_rule_ref="RULE-010"),
    "成交金额": dict(canonical_field="amount", status="CONFIRMED",
                  rationale="人工确认业务规则 RULE-010：该字段记录人民币（CNY）金额，标准化为 "
                            "amount_original/currency_original=CNY/amount_cny（无需换算）。"
                            "此前因未标注币种被标记 REVIEW_REQUIRED，RULE-010 已解决该口径分歧。",
                  rule_evidence=RULE_010, output_fields=AMOUNT_OUTPUT_FIELDS, value_rule_ref="RULE-010"),
    "跟进反馈": dict(canonical_field=None, status="EXCLUDED_BY_BUSINESS_RULE",
                  rationale="人工确认业务规则 RULE-011：该字段不是本次客户需求趋势分析所需的核心数据，"
                            "不进入统一分析数据集。原始 Excel 文件中的列保留不动，仅不纳入 unified_dataset。",
                  rule_evidence=RULE_011),
    "客户备注": dict(canonical_field=None, status="EXCLUDED_BY_BUSINESS_RULE",
                  rationale="人工确认业务规则 RULE-011：该字段不是本次客户需求趋势分析所需的核心数据，"
                            "不进入统一分析数据集（该字段在其出现的两个 source 中恰好也均为 100% 空值，"
                            "但排除的依据是 RULE-011 本身，与是否为空无关）。",
                  rule_evidence=RULE_011),
    "进度": dict(canonical_field="order_status", status="CONFIRMED",
                rationale="字段名清晰，全部出现场景语义一致（订单/案例进展状态）。", rule_evidence=None),
    "客服": dict(canonical_field="consultant_name", status="CONFIRMED",
                rationale="仅出现于顾问部（source_002/004/006），学管部无对应字段；这是部门特有字段"
                          "（结构性缺席，非映射歧义），语义清晰（负责顾问/客服姓名）。", rule_evidence=None),
    "未成交原因": dict(canonical_field=None, status="EXCLUDED_BY_BUSINESS_RULE",
                   rationale="人工确认业务规则 RULE-011：该字段不是本次客户需求趋势分析所需的核心数据，"
                             "不进入统一分析数据集。原始 Excel 文件中的列保留不动，仅不纳入 unified_dataset。",
                   rule_evidence=RULE_011),
}

CANONICAL_GLOSSARY = {
    "consultation_date": "咨询/记录发生的主日期",
    "country": "客户意向留学国家",
    "school": "客户意向学校/院校",
    "degree_level": "客户学历层次（RULE-012：大一～大四归一为「本科」，保留 degree_level_original）",
    "major": "客户意向专业/课程方向",
    "deadline": "任务/作业截止日期（DDL）",
    "task_type": "作业/咨询任务类型（RULE-008 合并 作业形式/作业类型/咨询内容，仅字段级，值级未确认）",
    "channel": "客户来源渠道/类型（RULE-007 合并 客户来源/客户类型）",
    "order_id": "订单/记录唯一编号",
    "amount": "订单/成交金额（RULE-009/RULE-010：产出 amount_original/currency_original/amount_cny，"
              "AUD 按固定汇率 4.5 换算，CNY 不换算）",
    "order_status": "订单/案例进展状态",
    "consultant_name": "负责顾问/客服姓名（顾问部特有字段）",
    "[EXCLUDED] 客户备注/跟进反馈/未成交原因": "RULE-011：不进入本项目分析 Schema，原始文件保留不动",
}


def build(run_id: str):
    artifacts_dir = ROOT / "runs" / run_id / "artifacts"
    manifest = json.loads((artifacts_dir / "source_manifest.json").read_text(encoding="utf-8"))

    business_rules_md = ROOT / "policies" / "business_rules.md"
    rules_yaml_path = ROOT / "config" / "data" / "standardization_rules.yaml"
    assert business_rules_md.exists(), "Required Shared Rule missing: policies/business_rules.md"
    rules = yaml.safe_load(rules_yaml_path.read_text(encoding="utf-8"))
    rule_ids = {r["rule_id"] for r in rules["rules"] if r["status"] == "ACTIVE"}
    schema_mapping_rules = {
        r["rule_id"]: r for r in rules["rules"]
        if "schema_mapping_agent" in r.get("scope", []) and r["status"] == "ACTIVE"
    }
    assert set(schema_mapping_rules) >= RULE_IDS_BACKING_MAPPINGS, (
        f"expected ACTIVE rules {RULE_IDS_BACKING_MAPPINGS} in scope for Schema Mapping Agent, "
        f"found {set(schema_mapping_rules)}"
    )

    items = []
    unresolved = []
    inputs = [
        {"artifact": "source_manifest.json", "run_id": run_id, "version": manifest["version"]},
        {"artifact": "policies/business_rules.md", "version": "2.0"},
        {"artifact": "config/data/standardization_rules.yaml", "rules_version": rules["rules_version"]},
    ]

    for source in manifest["sources"]:
        if source["status"] != "RECEIVED":
            continue  # nothing to map for non-received sources
        source_id = source["source_id"]
        profile = json.loads((artifacts_dir / "source_profiles" / f"{source_id}.json").read_text(encoding="utf-8"))
        inputs.append({"artifact": f"source_profiles/{source_id}.json", "run_id": run_id})

        for sheet_name, sheet in profile["sheets"].items():
            for field in sheet["fields"]:
                raw_name = field["field_name"]
                item_id = f"{source_id}.{raw_name}"
                entry = MAPPING_TABLE.get(raw_name)

                evidence_refs = [
                    {"type": "source_profile_field", "source_id": source_id,
                     "artifact": f"source_profiles/{source_id}.json",
                     "field_name": raw_name, "dtype": field["dtype"],
                     "missing_rate": field["missing_rate"]}
                ]

                item = {
                    "id": item_id,
                    "source_id": source_id,
                    "raw_field_name": raw_name,
                }

                if entry is None:
                    item.update(canonical_field=None, status="UNMAPPED",
                                rationale=f"字段名「{raw_name}」未匹配任何已知映射规则或结构证据，无法确定合理映射。")
                else:
                    assert entry["status"] in VALID_STATUSES, f"invalid status in MAPPING_TABLE: {entry}"
                    rule_evidence = entry.get("rule_evidence")
                    if rule_evidence:
                        assert rule_evidence["rule_id"] in rule_ids, f"unknown rule_id referenced: {rule_evidence}"
                        assert entry["status"] in ("CONFIRMED", "EXCLUDED_BY_BUSINESS_RULE"), (
                            f"field backed by ACTIVE manual_business_confirmation rule "
                            f"{rule_evidence['rule_id']} must be CONFIRMED or EXCLUDED_BY_BUSINESS_RULE, "
                            f"not {entry['status']} (human-confirmed rules outrank model inference, per "
                            f"docs/AGENT_CONTRACT.md section 11 — 已人工确认的字段不得重新标记为 REVIEW_REQUIRED)"
                        )
                        evidence_refs.insert(0, rule_evidence)

                    item.update(
                        canonical_field=entry["canonical_field"],
                        status=entry["status"],
                        rationale=entry["rationale"],
                    )
                    if "output_fields" in entry:
                        item["output_fields"] = entry["output_fields"]
                    if "value_rule_ref" in entry:
                        item["value_rule_ref"] = entry["value_rule_ref"]

                item["evidence_refs"] = evidence_refs
                items.append(item)

                if item["status"] in ("REVIEW_REQUIRED", "UNMAPPED"):
                    unresolved.append({"id": item_id, "status": item["status"], "reason": item["rationale"]})

    generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    status_counts = {s: 0 for s in VALID_STATUSES}
    for it in items:
        status_counts[it["status"]] += 1

    mapping = {
        "run_id": run_id,
        "agent": "Schema Mapping Agent",
        "wave": "W2",
        "version": 1,
        "generated_at": generated_at,
        "status": "COMPLETED",
        "inputs": inputs,
        "canonical_field_glossary": [
            {"canonical_field": k, "definition": v} for k, v in CANONICAL_GLOSSARY.items()
        ],
        "items": items,
        "status_counts": status_counts,
        "evidence_refs": [
            {"type": "artifact", "ref": "source_manifest.json"},
            {"type": "artifact", "ref": "policies/business_rules.md"},
            {"type": "artifact", "ref": "config/data/standardization_rules.yaml"},
        ],
        "unresolved": unresolved,
        "notes": [
            "本轮只做字段语义映射（字段名 -> 标准字段名 / 排除标记），未做任何值级标准化（含汇率换算、学历归一、日期解析），"
            "未修改任何原始数据或已产出的 source_profiles。",
            "RULE-007～RULE-010、RULE-012 覆盖的字段已直接采用规则结论并标记 CONFIRMED；RULE-011 覆盖的字段标记 "
            "EXCLUDED_BY_BUSINESS_RULE。人工确认规则优先级高于模型推理，均不得重新标记为 REVIEW_REQUIRED。",
            "RULE-008 仅确认字段级等价，task_type 内部具体取值（如 essay/补考/包课等）的标准化尚未人工确认，"
            "本 Agent 未涉及、未处理任何取值层面的归并。",
            "RULE-009/RULE-010 已解决此前 amount 字段因跨 source 币种标注不一致导致的 REVIEW_REQUIRED；"
            "实际汇率换算（AUD×4.5）由 Data Standardization Agent 执行，本 Agent 只做分类归属。",
        ],
    }

    out_path = artifacts_dir / "schema_mapping.json"
    out_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    return mapping


if __name__ == "__main__":
    run_id = sys.argv[1] if len(sys.argv) > 1 else os.environ["CDAT_RUN_ID"]
    result = build(run_id)
    print(json.dumps({
        "run_id": result["run_id"],
        "status_counts": result["status_counts"],
        "unresolved_count": len(result["unresolved"]),
    }, ensure_ascii=False, indent=2))
