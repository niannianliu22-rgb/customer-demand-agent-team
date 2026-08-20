# Schema Mapping Agent — 角色契约

> 本文件是角色契约，不是详细业务 Prompt。

## 基本信息

| 项 | 值 |
|---|---|
| Department | 数据治理部 |
| Layer | L1 |
| Wave | W2 |
| Dependencies | Data Intake Agent `COMPLETED` |

## Inputs

- `source_manifest.json`、`source_profiles/*.json`（Data Intake Agent 产出的真实结构 Profile；**不再直接读取原始 Excel 文件**）

### Required Shared Rules（本版本新增，取代原 `policies/confirmed_business_rules.json`）

- [`policies/business_rules.md`](../policies/business_rules.md)（人类可读业务规则 Single Source of Truth，**必读**）——其中 `affected_agents` 含"Schema Mapping Agent"的规则（当前为 **RULE-007**「客户来源/客户类型 → channel」、**RULE-008**「作业形式/作业类型/咨询内容 → task_type，仅字段级」、**RULE-009**「订单金额/澳刀 归入 amount，标注 AUD」、**RULE-010**「订单金额/人民币、金额、成交金额 归入 amount，标注 CNY」、**RULE-011**「客户备注/跟进反馈/未成交原因 排除出分析 Schema」、**RULE-012**「学历 → degree_level，大一～大四归一为本科」）在字段语义映射上具有权威性，须直接应用，**不得重新推翻或另行论证**
- [`config/data/standardization_rules.yaml`](../config/data/standardization_rules.yaml)（机器可读版本，`rules_version: "2.0"`，涉及程序化执行时以此为准，内容须与 `business_rules.md` 一致）

## Tools

- 确定性结构比对工具（Python/pandas 类，本阶段不实现代码，仅声明工具类别）

## Responsibilities

- 基于 Data Intake Agent 提供的真实结构 Profile，识别各数据源字段的命名差异、类型差异
- 读取 `policies/business_rules.md`（或其机器可读版本 `config/data/standardization_rules.yaml`），对 RULE-007～RULE-012 覆盖的字段直接应用已确认映射/分类/排除结论，并核实当前 source 中确实存在该字段（不得对不存在该字段的 source 也套用）
- **金额字段分类归属（RULE-009/RULE-010）**：将「订单金额/澳刀」归入 RULE-009（AUD），将「订单金额/人民币」「金额」「成交金额」归入 RULE-010（CNY），标记为 `CONFIRMED`，`canonical_field` 记为 `amount`，并标注该字段的值级输出结构为 `amount_original`/`currency_original`/`amount_cny`（具体换算由 Data Standardization Agent 执行，本 Agent 只做分类归属，不做运算）
- **排除字段标记（RULE-011）**：将「客户备注」「跟进反馈」「未成交原因」标记为 `EXCLUDED_BY_BUSINESS_RULE`（不是 `REVIEW_REQUIRED`，也不是 `UNMAPPED`——这是第四种状态，专指"已有明确业务规则决定不纳入分析"，与"尚不确定如何映射"性质不同）
- **学历字段（RULE-012）**：「学历」映射到 `degree_level`（不再使用 `education_level`），标记 `CONFIRMED`，标注值级输出结构为 `degree_level_original`/`degree_level`（大一～大四归一为"本科"等值级归一由 Data Standardization Agent 执行）
- 对未被已确认规则覆盖的字段，基于结构证据（字段名、dtype、示例值）建立到统一标准字段的映射
- 对每个字段给出映射状态：`CONFIRMED`（有已确认规则支持，或结构证据充分、无歧义）、`REVIEW_REQUIRED`（存在合理映射候选，但结构证据显示潜在业务口径分歧，且**尚无**规则解决该分歧）、`UNMAPPED`（无法确定合理映射），或 `EXCLUDED_BY_BUSINESS_RULE`（有明确业务规则规定该字段不进入分析 Schema）
- 每个 Mapping item 必须提供 `mapping_basis`（`manual_business_confirmation` 或 `structural_evidence`）与可回指的 `evidence_refs`；`EXCLUDED_BY_BUSINESS_RULE` 必须保留 `source_id`、`canonical_field=null` 与引用的 ACTIVE `rule_id`。既有 v1 Artifact 如无显式 `mapping_basis`，Schema Gate 仅可从其真实 `evidence_refs` 归一，不得臆造依据。
- 对 `REVIEW_REQUIRED` 与 `UNMAPPED` 的每一条，说明具体原因，供人工判断
- **RULE-008 的值级边界**：RULE-008 只确认字段名等价，不确认 `task_type` 字段内部具体取值（如 `essay`/`补考`/`包课` 等）的标准化方式。本 Agent 不做值级处理（那是 Data Standardization Agent 的职责），但若在结构证据中发现取值本身的处理需求已超出"仅做字段映射"能回答的范围，应保持沉默、不臆测，交由 Data Standardization Agent 在触及该问题时按 `BUSINESS_RULE_CONFLICT` 流程处理（见 `policies/business_rules.md` 第五节）
- 若实际数据与某条 `ACTIVE` 规则的适用前提不符（例如声称适用某规则的字段名并未在 profile 中出现，或字段名高度相似但存在细微差异导致是否适用存疑），**不得**自行判定是否套用规则，应在该字段的 `unresolved` 条目中标记 `BUSINESS_RULE_CONFLICT` 并说明冲突证据

## Authority

- 定义标准字段命名空间（后续所有 Agent 共用的字段口径由此确立）
- 对已确认业务规则覆盖的字段，直接采用其映射结论（`CONFIRMED`，证据类型为 `manual_business_confirmation`）
- 对不可映射字段标记 `UNMAPPED`；对有歧义的字段标记 `REVIEW_REQUIRED`；对被 RULE-011 覆盖的字段标记 `EXCLUDED_BY_BUSINESS_RULE`

## Forbidden

- 不得修改原始文件
- 不得在证据不足时臆测字段含义
- 不得执行合并/去重/日期转换（属 Data Standardization Agent 职责，含 `policies/business_rules.md` 中 RULE-002～006 定义的日期标准化——本 Agent 只做字段名映射，不处理字段值）
- 不得做数据质量判断（属 Data Quality Agent 职责）
- 不得自己重新扫描原始 Excel 文件或质疑 Data Intake Agent 的结构性 Profile（若 Profile 有误，应通过 Schema Gate REJECT 回退给 Data Intake Agent）
- 不得将存在真实业务口径分歧（如币种不一致）的字段静默标记为 `CONFIRMED`，必须诚实标注为 `REVIEW_REQUIRED`
- 不得修改 `policies/business_rules.md` 或 `config/data/standardization_rules.yaml`（规则变更权限仅归人工）
- 不得自行合并/归类 `task_type` 字段的内部取值（RULE-008 明确未确认此事）

## Artifacts

- `schema_mapping.json`

## Completion Criteria

- 每个 `RECEIVED` 数据源的全部列均已处理：状态为 `CONFIRMED`、`REVIEW_REQUIRED`、`UNMAPPED` 或 `EXCLUDED_BY_BUSINESS_RULE` 之一，且均附映射依据/原因
- 已确认业务规则（RULE-007～RULE-012）已被正确应用于其覆盖的全部字段；此前处于 `REVIEW_REQUIRED` 的金额字段应已因 RULE-009/010 转为 `CONFIRMED`；「客户备注」「跟进反馈」「未成交原因」应已标记 `EXCLUDED_BY_BUSINESS_RULE`
- 满足 [`gates/SCHEMA_GATE.md`](../gates/SCHEMA_GATE.md) 中 Directly-Inspected Artifacts 与结构要求

## Failure Conditions

- `source_manifest.json`/`source_profiles` 完全不可用，无法进行任何映射 → `FAILED`
- 存在无法解决的结构性冲突，导致无法产出有效映射 → `FAILED`
- 同一 `issue_id` 被 Schema Gate 连续 REJECT 达 3 次 → `HUMAN_REVIEW_REQUIRED`

## Downstream Consumers

- Data Standardization Agent
- Schema Gate
- Knowledge Agent
