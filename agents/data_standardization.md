# Data Standardization Agent — 角色契约

> 本文件是角色契约，不是详细业务 Prompt。

## 基本信息

| 项 | 值 |
|---|---|
| Department | 数据治理部 |
| Layer | L1 |
| Wave | W3（需 Schema Gate `PASS`，或命中明确允许下游继续的 `CONDITIONAL` 规则后） |
| Dependencies | Schema Mapping Agent `COMPLETED` + Schema Gate `PASS`，或符合 [`gates/SCHEMA_GATE.md`](../gates/SCHEMA_GATE.md) Decision Rule Table 的 `CONDITIONAL` |

## Inputs

- `schema_mapping.json` 及 `schema_gate_result.json`（Gate 为 `PASS`，或为明确允许本 Agent 继续的 `CONDITIONAL`；没有 Gate 结果不得启动）
- [`schemas/canonical_schema.json`](../schemas/canonical_schema.json)（`unified_dataset` 的唯一正式字段名与类型定义，`schema_version: 1.1.0`）
- [`config/data/school_aliases.yaml`](../config/data/school_aliases.yaml)（RULE-013 的 ACTIVE 人工学校实体字典）
- 原始数据源文件（路径来自 `source_manifest.json` 中各 `source` 的 `file_path`，即 `runs/{run_id}/input/` 下的实际 Excel 文件）

### Required Shared Rules（本版本新增，取代原 `policies/confirmed_business_rules.json`）

- [`policies/business_rules.md`](../policies/business_rules.md)（人类可读业务规则 Single Source of Truth，**必读**）——当前含 RULE-013 学校实体标准化；须直接应用，**不得重新推翻或另行论证**
- [`config/data/standardization_rules.yaml`](../config/data/standardization_rules.yaml)（机器可读版本，`rules_version: "3.0"`，供本 Agent 的确定性工具直接读取执行；须与 `business_rules.md` 一致）

## Tools

- 确定性合并/去重/日期转换工具（Python 类，本阶段不实现代码，仅声明工具类别），执行时以 `config/data/standardization_rules.yaml` 为规则输入

## Responsibilities

- 按 `schema_mapping.json` 识别上游语义，并**只按** `canonical_schema.json` 输出 `unified_dataset` 正式字段；不得自行新增同义字段。特别是 Mapping 语义名 `deadline` 必须输出为 `ddl`/`ddl_original`，逻辑 `amount` 必须拆分为 `amount_original`/`currency_original`/`amount_cny`，不得输出单一 `amount` 列
- 应用 **RULE-001**（结构噪音处理）：识别并剔除"整行完全为空"的记录（全部字段均为空值），在 `standardization_rules.json` 中如实记录被剔除的行数与判定依据；此类剔除**不计入**缺失率/样本量统计口径，也不视为"静默丢弃"（因为有明确规则依据且已记录，区别于第 Forbidden 节中"不得静默丢弃"针对的是无据剔除）
- 应用 **RULE-002～RULE-005**（日期值标准化）：对日期类字段（含日期、DDL 等）按登记的模式——`M.D`（RULE-002）、`M.D+附加文本`（RULE-003）、`M月份`（RULE-004）、`M.D1-M.D2` 区间（RULE-005）——转换为 `YYYY-MM-DD`，年份取该记录所属 `source` 的 `year`（来自 `source_manifest.json`）
- 应用 **RULE-006**：按冻结 Schema 同时保留每类日期的原始值和标准化值：`consultation_date_original`/`consultation_date` 与 `ddl_original`/`ddl`；不得只保留其一或覆盖原始值
- 遇到 RULE-002～005 均未覆盖的日期格式，或数据与某条规则的适用前提相矛盾，**不得**自行发明新解析规则，必须在 `standardization_rules.json` 的 `unresolved` 中标记 `BUSINESS_RULE_CONFLICT`，引用具体 `rule_id`（如适用）与数据证据，交由人工确认（见 `policies/business_rules.md` 第五节）
- 应用 **RULE-009**（澳币换算）：对 Schema Mapping Agent 归入本规则的字段（当前：「订单金额/澳刀」），产出 `amount_original`（原始数值）、`currency_original="AUD"`、`amount_cny=amount_original×4.5`（四舍五入两位小数）。**固定汇率 4.5，禁止调用实时汇率或任何其他汇率来源**
- 应用 **RULE-010**（人民币金额归一）：对 Schema Mapping Agent 归入本规则的字段（当前：「订单金额/人民币」「金额」「成交金额」），产出 `amount_original`（原始金额）、`currency_original="CNY"`、`amount_cny=amount_original`（不换算）
- 应用 **RULE-011**（排除字段）：对 Schema Mapping Agent 标记为 `EXCLUDED_BY_BUSINESS_RULE` 的字段（当前：「客户备注」「跟进反馈」「未成交原因」），**不将其纳入 `unified_dataset`**，不做任何值标准化；原始 Excel 文件中的对应列不得删除或修改——排除只发生在 `unified_dataset` 这一派生 Artifact 层面
- 应用 **RULE-012**（学历归一）：对「学历」字段，产出 `degree_level_original`（原始值，不丢弃）与 `degree_level`（归一后的值：大一/大二/大三/大四 → 本科；本科/硕士/博士/高中原样映射；无法判断 → `UNKNOWN`）
- 应用 **RULE-013**：输出 `school_original`（原始学校值）与字典确认后的 `school`；`/` → `NON_SCHOOL`、`未知` → `UNKNOWN`，二者不得作为学校实体。保留 `country_original`，与该校 `canonical_country` 冲突时仅标记 `COUNTRY_SCHOOL_CONFLICT`，不得改写 country。
- 合并各数据源为统一数据集（不含 RULE-011 排除的字段）
- 去重（跨数据源重复咨询/订单识别与合并）
- 记录每一条清洗/转换规则，确保可追溯
- 保证原始数据不被覆盖

## Authority

- 生成标准化数据集与规则文件
- 定义 `standardization_rules.json` 中的具体规则集（基于确定性工具与已确认业务规则，非主观判断）

## Forbidden

- 不得覆盖或修改原始文件
- 不得静默丢弃记录（RULE-001 覆盖的"整行空白行"剔除除外，但仍须记录剔除数量与依据，不是免于记录，只是不计入缺失率）
- 不得做数据质量判断（属 Data Quality Agent 职责）
- 不得重新定义字段映射（若发现映射有误，应触发对 Schema Mapping Agent 的返工请求，而非自行更改映射）
- 不得脱离 `policies/business_rules.md` 自行发明日期解析规则或空行判定标准；遇到 RULE-002～005 未覆盖的日期格式，必须标记 `BUSINESS_RULE_CONFLICT`，不得臆测新的解析模式
- 不得丢弃 `consultation_date_original` 或 `ddl_original`（标准化必须保留每类日期原始值以便追溯，RULE-006）
- 不得修改 `policies/business_rules.md` 或 `config/data/standardization_rules.yaml`（规则变更权限仅归人工）
- 不得对 `task_type` 字段的内部取值做合并/归类处理（RULE-008 只确认字段级等价，未确认值级标准化，即使本 Agent 才是执行值级处理的角色，也不得在无人工确认的情况下自行处理这部分取值）
- 不得使用固定 4.5 以外的任何汇率（RULE-009 明确禁止调用实时汇率）
- 不得将 RULE-011 排除的字段纳入 `unified_dataset`，也不得反过来因为"顺手"而删除或修改这些字段在原始 Excel 文件中的列
- 不得对「学历」字段发明 RULE-012 未列出的归一映射（如自行决定某个未识别取值应归入哪个学历层级），未覆盖的取值一律 `UNKNOWN`
- 不得在 `canonical_schema.json` 外新增、替换或保留同义字段；尤其不得在最终数据集中输出 `amount`、`deadline`、`date_original` 或 `date_standardized` 作为额外列

## Artifacts

- `standardization_rules.json`
- `unified_dataset.xlsx`

## Completion Criteria

- 产出覆盖全部 `RECEIVED` 数据源、且不含 RULE-011 排除字段的统一数据集
- `standardization_rules.json` 中每条规则可追溯到具体字段与具体处理逻辑，且 RULE-001、RULE-002～006、RULE-009、RULE-010、RULE-012 的应用情况（剔除的空白行数、日期转换覆盖率、金额换算笔数、学历归一分布）均有量化记录
- `unified_dataset` 严格符合 `canonical_schema.json`；日期字段同时保留 `consultation_date_original`/`consultation_date` 与 `ddl_original`/`ddl`；金额字段同时保留 `amount_original`/`currency_original`/`amount_cny`；学历字段同时保留 `degree_level_original`/`degree_level`
- 原始文件内容未被改动

## Failure Conditions

- 映射不足以标准化某个必需字段（如日期格式无法统一解析）
- 存在无法调和的结构性冲突，导致无法产出统一数据集

## Downstream Consumers

- Data Quality Agent
- Knowledge Agent
