#!/usr/bin/env python3
"""Create human-review-only candidates for every unresolved school value.

This script is intentionally conservative: its output is a proposal artifact,
not an update to the ACTIVE school alias dictionary or any dataset.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = ROOT / "runs/RUN-202608-DEMAND-001/artifacts/dimension_review"

# original_value: (suggested canonical name, suggested country, classification, reason)
PROPOSALS = {
    "利兹": ("University of Leeds", "英国", "PROPOSED_HIGH", "中文常用简称；与英国学校名称唯一对应。"),
    "伯明翰": ("University of Birmingham", "英国", "PROPOSED_MEDIUM", "城市简称；通常指伯明翰大学，但亦可能指其他伯明翰院校。"),
    "莫纳什": ("Monash University", "澳洲", "PROPOSED_HIGH", "中文译名与英文正式校名唯一对应。"),
    "布里斯托": ("University of Bristol", "英国", "PROPOSED_HIGH", "中文常用简称；与英国学校名称唯一对应。"),
    "杜伦": ("Durham University", "英国", "PROPOSED_HIGH", "中文常用简称；与英国学校名称唯一对应。"),
    "爱丁堡": ("The University of Edinburgh", "英国", "PROPOSED_MEDIUM", "城市简称；通常指爱丁堡大学，但需排除其他爱丁堡院校。"),
    "诺丁汉": ("University of Nottingham", "英国", "PROPOSED_MEDIUM", "城市简称；通常指诺丁汉大学，但存在其他同城院校。"),
    "埃克塞特": ("University of Exeter", "英国", "PROPOSED_HIGH", "中文常用简称；与英国学校名称唯一对应。"),
    "赫瑞瓦特": ("Heriot-Watt University", "英国", "PROPOSED_HIGH", "中文译名与英文正式校名唯一对应。"),
    "迪肯": ("Deakin University", "澳洲", "PROPOSED_HIGH", "中文常用简称；与澳洲大学唯一对应。"),
    "卡迪夫": ("Cardiff University", "英国", "PROPOSED_MEDIUM", "城市简称；通常指卡迪夫大学，仍需人工确认实体。"),
    "多伦多": ("University of Toronto", "加拿大", "PROPOSED_MEDIUM", "城市简称；通常指多伦多大学，但存在其他多伦多院校。"),
    "德蒙": ("De Montfort University", "英国", "PROPOSED_HIGH", "中文简称与 De Montfort University 常用译名一致。"),
    "拉夫堡": ("Loughborough University", "英国", "PROPOSED_HIGH", "中文常用简称；与英国学校名称唯一对应。"),
    "波士顿": ("", "", "REVIEW_REQUIRED", "仅为城市名；可能对应 Boston University、Boston College 等，无法唯一确定。"),
    "雷丁": ("University of Reading", "英国", "PROPOSED_HIGH", "中文常用简称；与英国学校名称唯一对应。"),
    "香港科技大学": ("The Hong Kong University of Science and Technology", "香港", "PROPOSED_HIGH", "完整中文校名。"),
    "LSE": ("London School of Economics and Political Science", "英国", "PROPOSED_HIGH", "国际通用英文缩写，唯一对应。"),
    "东北大学": ("Northeastern University", "美国", "PROPOSED_MEDIUM", "中文名存在中国/美国同名学校；来源国家为美国仅作辅助证据。"),
    "利物浦": ("University of Liverpool", "英国", "PROPOSED_MEDIUM", "城市简称；通常指利物浦大学，需排除同城院校。"),
    "弗林德斯": ("Flinders University", "澳洲", "PROPOSED_HIGH", "中文译名与澳洲大学唯一对应。"),
    "托伦斯大学": ("Torrens University Australia", "澳洲", "PROPOSED_HIGH", "完整中文校名。"),
    "曼彻斯特城市大学": ("Manchester Metropolitan University", "英国", "PROPOSED_HIGH", "完整中文校名。"),
    "浸会大学": ("Hong Kong Baptist University", "香港", "PROPOSED_HIGH", "香港语境下的常用简称。"),
    "港浸会": ("Hong Kong Baptist University", "香港", "PROPOSED_HIGH", "香港浸会大学常用简称。"),
    "皇家霍洛威": ("Royal Holloway, University of London", "英国", "PROPOSED_HIGH", "中文常用简称，唯一对应。"),
    "维多利亚": ("", "", "REVIEW_REQUIRED", "可能指 University of Victoria、Victoria University 或地区名；现有 country 值冲突，无法唯一确定。"),
    "考文垂": ("Coventry University", "英国", "PROPOSED_MEDIUM", "城市简称；通常指考文垂大学，需人工确认。"),
    "萨里大学": ("University of Surrey", "英国", "PROPOSED_HIGH", "完整中文校名。"),
    "阿伯丁": ("University of Aberdeen", "英国", "PROPOSED_MEDIUM", "城市简称；通常指阿伯丁大学，需排除其他同城院校。"),
    "香港恒生": ("The Hang Seng University of Hong Kong", "香港", "PROPOSED_HIGH", "香港恒生大学常用简称。"),
    "HK U": ("The University of Hong Kong", "香港", "PROPOSED_HIGH", "英文缩写变体；与既有 ACTIVE 实体一致。"),
    "HKU": ("The University of Hong Kong", "香港", "PROPOSED_HIGH", "国际通用英文缩写；与既有 ACTIVE 实体一致。"),
    "JHU": ("Johns Hopkins University", "美国", "PROPOSED_HIGH", "国际通用英文缩写，唯一对应。"),
    "SIM": ("Singapore Institute of Management", "新加坡", "PROPOSED_HIGH", "新加坡教育机构常用英文缩写。"),
    "TUM": ("Technical University of Munich", "德国", "PROPOSED_HIGH", "国际通用英文缩写，唯一对应；country 值不作为否决依据。"),
    "UCD": ("", "", "REVIEW_REQUIRED", "缩写可能指 University College Dublin 或 University of California, Davis 等，无法仅凭当前值唯一确定。"),
    "UTS": ("University of Technology Sydney", "澳洲", "PROPOSED_HIGH", "澳洲大学通用英文缩写，唯一对应。"),
    "cmu": ("", "", "REVIEW_REQUIRED", "可能指 Carnegie Mellon University、Central Michigan University 等，无法唯一确定。"),
    "csm": ("Central Saint Martins", "英国", "PROPOSED_MEDIUM", "常指 Central Saint Martins（University of the Arts London 组成学院），需确认是否以学院还是 UAL 为分析实体。"),
    "othm": ("", "", "NON_SCHOOL", "OTHM 为资质授予机构/资格框架，不是具体学校实体。"),
    "pitt": ("University of Pittsburgh", "美国", "PROPOSED_HIGH", "国际常用简称，唯一对应。"),
    "psb": ("PSB Academy", "新加坡", "PROPOSED_HIGH", "新加坡教育机构常用简称。"),
    "psu": ("", "", "REVIEW_REQUIRED", "可能指 Pennsylvania State University、Portland State University 等，无法唯一确定。"),
    "ucla": ("University of California, Los Angeles", "美国", "PROPOSED_HIGH", "国际通用英文缩写，唯一对应。"),
    "uq": ("University of Queensland", "澳洲", "PROPOSED_HIGH", "英文大小写变体；与既有 ACTIVE 实体一致。"),
    "中外合办": ("", "", "NON_SCHOOL", "办学形式，不是学校实体。"),
    "伦敦大学": ("University of London", "英国", "PROPOSED_MEDIUM", "联邦大学体系名称，非具体成员院校；需确认是否保留该层级实体。"),
    "伦敦大学城市学院": ("City, University of London", "英国", "PROPOSED_HIGH", "历史正式中文校名；需在未来版本决定是否迁移至现行名称。"),
    "伯克利": ("", "", "REVIEW_REQUIRED", "可能指 University of California, Berkeley、Berkeley College 等，无法唯一确定。"),
    "兰卡": ("Lancaster University", "英国", "PROPOSED_HIGH", "兰卡斯特大学常用简称。"),
    "兰卡斯特": ("Lancaster University", "英国", "PROPOSED_HIGH", "中文常用简称；与英国学校名称唯一对应。"),
    "凯泽大学": ("Keiser University", "美国", "PROPOSED_HIGH", "完整中文校名。"),
    "利兹大学": ("University of Leeds", "英国", "PROPOSED_HIGH", "完整中文校名。"),
    "加州大学": ("", "", "REVIEW_REQUIRED", "加州大学系统而非具体校区，无法作为唯一学校实体。"),
    "北卡": ("", "", "REVIEW_REQUIRED", "可能指 University of North Carolina 的不同校区，无法唯一确定。"),
    "华盛顿": ("", "", "REVIEW_REQUIRED", "可能指 University of Washington、Washington University in St. Louis 等，无法唯一确定。"),
    "南加州大学": ("University of Southern California", "美国", "PROPOSED_HIGH", "完整中文校名。"),
    "卡普兰": ("Kaplan Singapore", "新加坡", "PROPOSED_MEDIUM", "教育品牌而非唯一法人学校名称；结合来源国家提出候选，需人工确认。"),
    "卡普兰商学院": ("Kaplan Business School", "澳洲", "PROPOSED_HIGH", "完整中文校名。"),
    "哥伦比亚": ("Columbia University", "美国", "PROPOSED_MEDIUM", "通常指哥伦比亚大学，但名称可指其他实体；需人工确认。"),
    "哥大": ("Columbia University", "美国", "PROPOSED_HIGH", "哥伦比亚大学常用简称。"),
    "圣路易斯华盛顿": ("Washington University in St. Louis", "美国", "PROPOSED_HIGH", "中文常用校名，唯一对应。"),
    "坎特伯雷": ("University of Canterbury", "新西兰", "PROPOSED_MEDIUM", "城市/地区名；来源显示新西兰，提出该候选但需确认。"),
    "埃塞克斯": ("University of Essex", "英国", "PROPOSED_HIGH", "中文常用简称；与英国学校名称唯一对应。"),
    "堪培拉": ("University of Canberra", "澳洲", "PROPOSED_MEDIUM", "城市简称；通常指堪培拉大学，需人工确认。"),
    "多伦多高中": ("", "", "REVIEW_REQUIRED", "中学名称不完整，无法识别具体学校。"),
    "宁诺": ("University of Nottingham Ningbo China", "中国", "PROPOSED_HIGH", "宁波诺丁汉大学常用简称。"),
    "岭南大学": ("Lingnan University", "香港", "PROPOSED_HIGH", "完整中文校名。"),
    "悉尼": ("University of Sydney", "澳洲", "PROPOSED_MEDIUM", "城市简称；通常指悉尼大学，需排除其他悉尼院校。"),
    "悉尼科技大学": ("University of Technology Sydney", "澳洲", "PROPOSED_HIGH", "完整中文校名。"),
    "拉筹伯": ("La Trobe University", "澳洲", "PROPOSED_HIGH", "中文常用简称；与澳洲大学唯一对应。"),
    "教大": ("The Education University of Hong Kong", "香港", "PROPOSED_HIGH", "香港教育大学常用简称；与既有 ACTIVE 实体一致。"),
    "新南大学": ("University of New South Wales", "澳洲", "PROPOSED_HIGH", "新南威尔士大学的常见省略写法；与既有 ACTIVE 实体一致。"),
    "朴茨茅斯": ("University of Portsmouth", "英国", "PROPOSED_HIGH", "中文常用简称；与英国学校名称唯一对应。"),
    "杜伦大学": ("Durham University", "英国", "PROPOSED_HIGH", "完整中文校名。"),
    "梅西大学": ("Massey University", "新西兰", "PROPOSED_HIGH", "完整中文校名。"),
    "汤普森里佛斯": ("Thompson Rivers University", "加拿大", "PROPOSED_HIGH", "中文译名与加拿大大学唯一对应；country 值不作为否决依据。"),
    "港中文": ("The Chinese University of Hong Kong", "香港", "PROPOSED_HIGH", "香港中文大学常用简称。"),
    "港理": ("The Hong Kong Polytechnic University", "香港", "PROPOSED_HIGH", "香港理工大学常用简称；与既有 ACTIVE 实体一致。"),
    "港理工": ("The Hong Kong Polytechnic University", "香港", "PROPOSED_HIGH", "香港理工大学常用简称；与既有 ACTIVE 实体一致。"),
    "港科大": ("The Hong Kong University of Science and Technology", "香港", "PROPOSED_HIGH", "香港科技大学常用简称。"),
    "澳国立大学": ("Australian National University", "澳洲", "PROPOSED_HIGH", "中文校名变体；与既有 ACTIVE 实体一致。"),
    "澳大利亚国立": ("Australian National University", "澳洲", "PROPOSED_HIGH", "中文校名省略写法；与既有 ACTIVE 实体一致。"),
    "玛丽女王": ("Queen Mary University of London", "英国", "PROPOSED_HIGH", "Queen Mary University of London 常用中文简称；与既有 ACTIVE 实体一致。"),
    "电影": ("", "", "NON_SCHOOL", "学科/内容词，不是学校实体。"),
    "疑似谢菲": ("University of Sheffield", "英国", "PROPOSED_MEDIUM", "文本已表达谢菲尔德候选但带不确定语义，需人工确认。"),
    "科廷大学": ("Curtin University", "澳洲", "PROPOSED_HIGH", "完整中文校名。"),
    "约克大学": ("University of York", "英国", "PROPOSED_MEDIUM", "可能指英国 University of York 或加拿大 York University；现有历史 country 仅作辅助证据。"),
    "纽卡斯尔": ("Newcastle University", "英国", "PROPOSED_MEDIUM", "可能指英国或澳洲的 Newcastle University；既有 ACTIVE `纽卡` 指英国，但需人工确认。"),
    "维多利亚大学": ("Victoria University", "澳洲", "PROPOSED_MEDIUM", "名称存在加拿大同名大学；来源国家支持澳洲候选但仍需确认。"),
    "莫那什": ("Monash University", "澳洲", "PROPOSED_HIGH", "莫纳什的常见异体写法。"),
    "莱斯": ("Rice University", "美国", "PROPOSED_MEDIUM", "常指 Rice University，但简称可能存在歧义。"),
    "莱斯特": ("University of Leicester", "英国", "PROPOSED_HIGH", "中文常用简称；与英国学校名称唯一对应。"),
    "西澳": ("The University of Western Australia", "澳洲", "PROPOSED_HIGH", "西澳大学常用简称。"),
    "西澳大学": ("The University of Western Australia", "澳洲", "PROPOSED_HIGH", "完整中文校名。"),
    "语言班": ("", "", "NON_SCHOOL", "课程/项目类型，不是学校实体。"),
    "贝尔法斯特": ("Queen's University Belfast", "英国", "PROPOSED_MEDIUM", "城市简称；通常指贝尔法斯特女王大学，需排除其他同城院校。"),
    "贝法": ("Queen's University Belfast", "英国", "PROPOSED_MEDIUM", "常见简称但可能指城市/其他机构，需人工确认。"),
    "迪肯大学": ("Deakin University", "澳洲", "PROPOSED_HIGH", "完整中文校名。"),
    "金史密斯学院": ("Goldsmiths, University of London", "英国", "PROPOSED_HIGH", "完整中文校名。"),
    "香港": ("", "", "NON_SCHOOL", "地区名，不是学校实体。"),
    "香港浸会": ("Hong Kong Baptist University", "香港", "PROPOSED_HIGH", "香港浸会大学常用简称。"),
    "香港浸会大学": ("Hong Kong Baptist University", "香港", "PROPOSED_HIGH", "完整中文校名。"),
    "香港科技": ("The Hong Kong University of Science and Technology", "香港", "PROPOSED_HIGH", "香港科技大学常用简称。"),
    "马来": ("", "", "NON_SCHOOL", "国家/地区截断值，不是学校实体。"),
    "高中": ("", "", "NON_SCHOOL", "学历层级，不是学校实体。"),
    "高等职业学校": ("", "", "NON_SCHOOL", "学校类型，不是具体学校实体。"),
    "麦唐纳国际学校": ("", "", "REVIEW_REQUIRED", "中文译名无法唯一对应具体国际学校，需人工提供英文名或所在地。"),
}


def main() -> None:
    source = REVIEW_DIR / "school_unstandardized_values.csv"
    aliases_path = ROOT / "config/data/school_aliases.yaml"
    rules_path = ROOT / "policies/business_rules.md"
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with aliases_path.open(encoding="utf-8") as handle:
        aliases = yaml.safe_load(handle)
    rules = rules_path.read_text(encoding="utf-8")
    if aliases.get("status") != "ACTIVE" or aliases.get("business_rules_version") != "3.0":
        raise ValueError("ACTIVE school aliases v3.0 are required")
    if "RULE-013" not in rules or "**Business Rules Version: 3.0**" not in rules:
        raise ValueError("Business Rules v3.0 RULE-013 is required")
    source_values = {row["original_value"] for row in rows}
    if source_values != set(PROPOSALS):
        raise ValueError(f"proposal coverage mismatch: missing={source_values-set(PROPOSALS)}, extra={set(PROPOSALS)-source_values}")

    output = REVIEW_DIR / "school_unstandardized_review_round2.csv"
    fieldnames = [
        "original_value", "count", "source_ids", "years", "departments", "country_values",
        "suggested_canonical_name", "suggested_canonical_country", "confidence", "reason",
        "human_decision", "human_canonical_name", "human_notes",
    ]
    proposed_rows = []
    for row in rows:
        name, country, confidence, reason = PROPOSALS[row["original_value"]]
        proposed_rows.append({
            **{key: row[key] for key in fieldnames[:6]},
            "suggested_canonical_name": name,
            "suggested_canonical_country": country,
            "confidence": confidence,
            "reason": reason,
            "human_decision": "",
            "human_canonical_name": "",
            "human_notes": "",
        })
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(proposed_rows)

    groups = defaultdict(lambda: {"original_values": [], "total_count": 0, "confidence": set(), "suggested_canonical_country": set()})
    for row in proposed_rows:
        name = row["suggested_canonical_name"]
        if not name:
            continue
        group = groups[name]
        group["original_values"].append({"original_value": row["original_value"], "count": int(row["count"])})
        group["total_count"] += int(row["count"])
        group["confidence"].add(row["confidence"])
        if row["suggested_canonical_country"]:
            group["suggested_canonical_country"].add(row["suggested_canonical_country"])
    summary = {
        "run_id": "RUN-202608-DEMAND-001",
        "artifact_type": "school_unstandardized_round2_candidate_summary",
        "status": "PROPOSED_ONLY",
        "total_unstandardized_unique_values": len(proposed_rows),
        "total_unstandardized_rows": sum(int(row["count"]) for row in proposed_rows),
        "classification_counts": {key: sum(row["confidence"] == key for row in proposed_rows) for key in ["PROPOSED_HIGH", "PROPOSED_MEDIUM", "REVIEW_REQUIRED", "NON_SCHOOL", "UNKNOWN"]},
        "candidate_canonical_school_count": len(groups),
        "candidate_groups": [
            {
                "suggested_canonical_name": name,
                "suggested_canonical_country": sorted(group["suggested_canonical_country"]),
                "confidence": sorted(group["confidence"]),
                "total_count": group["total_count"],
                "original_values": sorted(group["original_values"], key=lambda item: (-item["count"], item["original_value"])),
            }
            for name, group in sorted(groups.items(), key=lambda item: (-item[1]["total_count"], item[0]))
        ],
        "input": "runs/RUN-202608-DEMAND-001/artifacts/dimension_review/school_unstandardized_values.csv",
        "output": "runs/RUN-202608-DEMAND-001/artifacts/dimension_review/school_unstandardized_review_round2.csv",
        "dictionary_modified": False,
        "dataset_modified": False,
    }
    with (REVIEW_DIR / "school_unstandardized_candidate_summary_round2.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
