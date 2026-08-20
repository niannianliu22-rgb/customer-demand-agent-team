# Business Rules — Single Source of Truth

**Business Rules Version: 17.0**

> 本文件是全项目业务规则的**人类可读唯一真源（Single Source of Truth）**。任何人工确认的业务规则一经写入本文件并标记 `status: ACTIVE`，即对全部相关 Agent 具有约束力——不因对话上下文结束而失效，不因 Agent 更换底层模型而失效，不由任何 Agent 自行推翻。
>
> 机器可读版本见 [`config/data/standardization_rules.yaml`](../config/data/standardization_rules.yaml)（`rules_version: "17.0"`，与本文件版本号保持一致）。两份文件描述同一组规则，本文件为叙述与治理层面的真源，YAML 文件为 Agent/程序执行时读取的结构化版本；若两者内容出现不一致，以本文件为准，并应立即修正 YAML 文件使二者重新一致（不一致本身就是 `BUSINESS_RULE_CONFLICT`，见第五节）。

---

## 一、规则登记表

每条规则至少记录：`rule_id`、`rule_name`、`scope`、`business_definition`、`examples`、`source`（固定为 `manual_business_confirmation`）、`status`、`created_at`、`affected_agents`。

### RULE-001 — Fully Blank Rows（整行空白行排除）

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-001 |
| `rule_name` | fully_blank_rows_excluded |
| `scope` | 数据标准化、数据质量统计、Data Gate 判定 |
| `business_definition` | 整行完全为空（全部字段均为空值）的记录属于 Excel 结构噪音，不属于业务数据。此类行：不计入 `business_row_count`；不计入字段缺失率分母；不计入样本量；不作为 Data Quality 风险；不触发 `CONDITIONAL`/`REJECT`。**原始文件不得因此被删除或修改**——排除只发生在标准化/统计计算层面，原始 Excel 文件本身必须保持原样。 |
| `examples` | RUN-202608-DEMAND-001 的真实扫描发现：6 个数据源的已用区域内均存在完全空白的尾部行，数量介于 19～213 行不等（详见该 run 的 `source_profiles/*.json`），若不排除会系统性夸大缺失率、低估有效样本量。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent（Data Gate 作为规则模块同样必须遵循，见 [`gates/DATA_GATE.md`](../gates/DATA_GATE.md)） |

### RULE-002 — 日期 M.D 格式

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-002 |
| `rule_name` | date_pattern_month_dot_day |
| `scope` | 数据标准化（日期字段值处理） |
| `business_definition` | 形如 `M.D` 的日期表达式，月为 M、日为 D，标准化为 `{source.year}-MM-DD`。若原始日期本身不含年份信息，年份**必须**取该记录所属 `source` 的 `year` 字段（来自 `source_manifest.json`），不得使用系统当前年份或任何其他来源推断年份。 |
| `examples` | `8.1` → `{source.year}-08-01`；`8.25` → `{source.year}-08-25` |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent |

### RULE-003 — 日期包含附加文本

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-003 |
| `rule_name` | date_with_trailing_text |
| `scope` | 数据标准化（日期字段值处理） |
| `business_definition` | 日期字段中若包含非日期的附加文本（如状态说明词），提取其中明确的 `M.D` 日期部分，按 RULE-002 标准化；附加文本本身不参与日期解析，也不保留在 `date_standardized` 中。 |
| `examples` | `8.25due` → `{source.year}-08-25` |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent |

### RULE-004 — 仅月份

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-004 |
| `rule_name` | date_month_only |
| `scope` | 数据标准化（日期字段值处理） |
| `business_definition` | 日期字段仅提及月份、未指明具体日期时，业务规则规定统一取该月第 1 日。 |
| `examples` | `10月份` → `{source.year}-10-01` |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent |

### RULE-005 — 日期区间

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-005 |
| `rule_name` | date_range_take_start |
| `scope` | 数据标准化（日期字段值处理） |
| `business_definition` | 日期字段表达为区间（`M.D1-M.D2`）时，统一取区间起始日作为标准化日期。 |
| `examples` | `8.2-8.9` → `{source.year}-08-02` |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent |

### RULE-006 — 日期原始值保留

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-006 |
| `rule_name` | date_original_value_retained |
| `scope` | 数据标准化产出结构、数据质量核查 |
| `business_definition` | 标准化日期字段（应用 RULE-002～005）时，必须同时输出 `date_original`（原始值，不做任何改写）与 `date_standardized`（标准化后的值）。不得只保留其一，不得用标准化值覆盖或删除原始值。 |
| `examples` | 原始值 `8.25due`，`source.year=2023` → `date_original="8.25due"`，`date_standardized="2023-08-25"`（两个字段并存） |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent |

### RULE-007 — Channel 字段等义

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-007 |
| `rule_name` | channel_field_equivalence |
| `scope` | 字段语义映射 |
| `business_definition` | 原始字段「客户来源」与「客户类型」业务语义相同，统一映射为标准字段 `channel`。 |
| `examples` | source_001/003（学管部）使用「客户来源」；source_002/004/005/006 使用「客户类型」——均映射到 `channel`。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Schema Mapping Agent |

### RULE-008 — Task Type 字段等义

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-008 |
| `rule_name` | task_type_field_equivalence |
| `scope` | 字段语义映射（**仅限字段级**，不含字段内部取值） |
| `business_definition` | 原始字段「作业形式」「作业类型」「咨询内容」业务语义相同，统一映射为标准字段 `task_type`。**本规则只确认"这三个字段名指的是同一件事"这一字段级语义，不确认字段内部具体取值的标准化方式。** |
| `examples` | source_001/003/005（学管部）使用「作业形式」；source_004/006（顾问部）使用「作业类型」；source_002（顾问部 2023）使用「咨询内容」——均映射到 `task_type`。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Schema Mapping Agent |

**⚠️ RULE-008 的边界**：除 RULE-014～RULE-021 已明确人工确认的值与组件拆分外，`task_type` 字段内部的具体取值（如 `essay`、`补考`、`包课`、`毕业论文辅导`、`文献综述`、`润色修改` 等）应如何标准化/归并，**目前尚未人工确认**。任何 Agent（含 Data Standardization Agent 未来处理字段值时）**不得自行合并或归类**这些取值，遇到需要处理这些取值的场景，必须输出 `BUSINESS_RULE_CONFLICT`（见第五节），交由人工确认后再作为新规则登记。

### RULE-009 — 澳币金额统一换算人民币

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-009 |
| `rule_name` | aud_amount_converted_to_cny |
| `scope` | 字段语义映射（分类归属）+ 数据标准化（值级换算执行） |
| `business_definition` | 原始字段「订单金额/澳刀」记录的是实际澳币（AUD）收款金额。标准化后须产出三个字段：`amount_original`（原始数值，不改写）、`currency_original`（固定为 `AUD`）、`amount_cny`（`amount_original × 4.5`，四舍五入保留两位小数）。**本项目当前使用固定业务汇率 1 AUD = 4.5 CNY，不得调用实时汇率或任何其他汇率来源替换该规则。** |
| `examples` | `1111.11 AUD` → `amount_original=1111.11`，`currency_original="AUD"`，`amount_cny=5000.00` |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Schema Mapping Agent（识别「订单金额/澳刀」归入本规则）、Data Standardization Agent（执行换算并产出三字段） |

### RULE-010 — 人民币金额字段

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-010 |
| `rule_name` | cny_amount_fields |
| `scope` | 字段语义映射（分类归属）+ 数据标准化（值级归一执行） |
| `business_definition` | 原始字段「订单金额/人民币」「金额」「成交金额」均表示人民币（CNY）金额，无需汇率转换。标准化后统一产出：`amount_original`（原始金额）、`currency_original`（固定为 `CNY`）、`amount_cny`（等于 `amount_original`，不做换算）。 |
| `examples` | `2700`（成交金额，人民币）→ `amount_original=2700`，`currency_original="CNY"`，`amount_cny=2700`（或按原始精度保留，无需强制两位小数，因未发生换算） |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Schema Mapping Agent（识别「订单金额/人民币」「金额」「成交金额」归入本规则）、Data Standardization Agent（执行归一产出三字段） |

**RULE-009 与 RULE-010 共同解决了此前 `amount` 字段的 `REVIEW_REQUIRED` 状态**（跨 source 币种标注不一致的问题）：字段级映射现已明确，值级换算口径也已明确，`amount` 相关字段自本版本起应标记为 `CONFIRMED`。

### RULE-011 — 非需求分析字段排除

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-011 |
| `rule_name` | non_analysis_fields_excluded |
| `scope` | 字段语义映射（排除标记）+ 数据标准化（不进入统一数据集）+ 历史需求规律分析（不作为输入） |
| `business_definition` | 原始字段「客户备注」「跟进反馈」「未成交原因」不是本次客户需求趋势分析所需的核心数据，不进入本项目统一分析数据集。Schema Mapping 阶段须将其标记为 `EXCLUDED_BY_BUSINESS_RULE`；不进入 `unified_dataset`；不进行任何值标准化；不作为 Historical Demand Pattern Agent 的分析输入。**"排除"仅指不进入本项目分析 Schema，原始 Excel 文件中的这些列不得被删除或修改**——排除只发生在派生 Artifact（`unified_dataset` 等）层面。 |
| `examples` | source_001/003/005 的「跟进反馈」列、source_002/004 的「客户备注」列、source_004/006 的「未成交原因」列——均登记但不进入统一数据集。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Schema Mapping Agent、Data Standardization Agent、Historical Demand Pattern Agent |

### RULE-012 — 本科年级归一

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-012 |
| `rule_name` | undergraduate_year_normalized |
| `scope` | 数据标准化（值级归一执行），字段映射沿用既有的「学历」→ `degree_level` |
| `business_definition` | 「学历」字段标准化为 `degree_level`（原始值同时保留于 `degree_level_original`，不得丢弃）。若原始值为「大一」「大二」「大三」「大四」，统一归一为 `degree_level = 本科`（本项目第一版不单独分析本科具体年级，暂不生成 `year_level`）。其他明确学历原样映射：`本科→本科`、`硕士→硕士`、`博士→博士`、`高中→高中`。无法判断的取值 → `UNKNOWN`。 |
| `examples` | 「大二」→ `degree_level_original="大二"`，`degree_level="本科"`；「硕士」→ `degree_level_original="硕士"`，`degree_level="硕士"`；无法识别的取值 → `degree_level="UNKNOWN"` |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Schema Mapping Agent（字段映射沿用 `degree_level`）、Data Standardization Agent（执行值级归一） |

### RULE-013 — 学校实体标准化与国家一致性标记

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-013 |
| `rule_name` | school_entity_standardization |
| `scope` | 数据标准化、数据质量、Data Gate、历史需求规律分析 |
| `business_definition` | [`config/data/school_aliases.yaml`](../config/data/school_aliases.yaml) 是本项目学校实体的正式人工确认字典。字典中 `status: ACTIVE` 的 alias 必须标准化为其 `canonical_name`；`school_original` 必须保留原始 Excel 学校值，`school` 写入 canonical 学校名称。字典中的 `/` 分类为 `NON_SCHOOL`、`未知` 分类为 `UNKNOWN`：两者的 `school_original` 必须保留，但不得作为真实学校实体参与学校需求排名、聚合或趋势分析。人工确认的 school alias 优先于任何 Agent 模型推理；Agent 不得自行新增或合并 alias。 |
| `country_consistency_check` | 每个 canonical school 对应字典中的 `canonical_country`。标准化时保留 `country_original`；若其值与该校的 `canonical_country` 冲突，仅输出 `COUNTRY_SCHOOL_CONFLICT` 记录（含 source 行证据），**不得**静默修改 `country` 或 `country_original`。Country 标准化属于后续独立阶段。 |
| `examples` | `新南` / `新南威尔士` / `unsw` → `University of New South Wales`；`/` → `school_original="/"`, `school="NON_SCHOOL"`，不进入学校排名。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent、Data Gate、Historical Demand Pattern Agent |

### RULE-014 — 学年包与辅导年包独立订单类型

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-014 |
| `rule_name` | task_type_xuenianbao_and_fudao_nianbao_are_distinct |
| `scope` | task_type 值标准化、Data Quality、Data Gate、后续分析使用的任务类型维度 |
| `business_definition` | `学年包` 与 `辅导年包` 是两个独立的正式订单类型，**不得互相归并、替换或作为同义 alias**。原始值为 `学年包` 时，标准值必须为 `学年包`；原始值为 `辅导年包` 时，标准值必须为 `辅导年包`。 |
| `official_canonical_list` | `config/dimensions/task_type/canonical.csv`。该清单在原 66 个公司 Excel 值基础上，新增人工确认的 `学年包`（`MANUAL-TASK-TYPE-001`）；原始公司 Excel `official_order_types.xlsx` 未被修改。 |
| `examples` | `学年包` → `学年包`；`辅导年包` → `辅导年包`；`学年包` → `辅导年包` 为禁止映射。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent、Data Gate、Historical Demand Pattern Agent |

### RULE-015 — 支付动作文本的已确认 Task Type Alias

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-015 |
| `rule_name` | manually_confirmed_task_type_aliases_business_substance_first |
| `scope` | task_type 值标准化、Data Quality、Data Gate、后续分析使用的任务类型维度 |
| `business_definition` | 对下表**逐值**采用“业务实质优先于支付动作文本”的人工确认映射。原始值含 `充值`、`补款`、`定金`、`预存`，不得仅因该词面就判为 `NON_TASK`；但该结论仅适用于下表，**禁止泛化**到任何未经人工确认的新值。 |
| `official_canonical_list` | `config/dimensions/task_type/canonical.csv`。本版本新增 `预存`（`MANUAL-TASK-TYPE-002`）和 `毕业无忧`（`MANUAL-TASK-TYPE-003`）；既有 `包课`、`学年包` 继续为独立类型，且 RULE-014 的“学年包 ≠ 辅导年包”约束继续生效。 |
| `approved_aliases` | `预存` → `预存`；`SVIP预存` → `预存`；`vip充值` → `预存`；`包课补款` → `包课`；`预存升级学年包定金` → `学年包`；`毕业无忧定金` → `毕业无忧`。 |
| `unknown_values` | `/` → `UNKNOWN`；原始 task_type 空值 → `UNKNOWN`。两者不得自行推测为任何正式订单类型。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent、Data Gate、Historical Demand Pattern Agent |

### RULE-016 — MULTI_TASK 组件保留与标准化

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-016 |
| `rule_name` | multi_task_component_standardization |
| `scope` | task_type 值标准化、Data Quality、Data Gate、Historical Demand Pattern Agent |
| `business_definition` | 多任务原始值不得压缩为单一 `task_type`。保留 `task_type_original`，写入 `task_type_mode = MULTI_TASK`，并以原始出现顺序写入 `task_type_components`（JSON 数组）。数组中每个已确认组件必须是 `config/dimensions/task_type/canonical.csv` 中的正式类型。 |
| `component_standardization` | `N` 词、补写、续写等明确为写作任务时 → `essay`；`LR部分润色`、`大论文润色`等润色任务 → `润色-proofreading`；`数据分析` → `Analysis`；`演讲稿` → `presentation`；`quiz` → `online test-exam/quiz`；`answer` → `做题`；`作业` → `assignment`；`视频` → `video`。该规则只适用于本次审核已列明的 MULTI_TASK 原始值，禁止对其他新值泛化。 |
| `unresolved_component_handling` | 某子任务不在当前官方清单中、或不能按 ACTIVE 规则唯一映射时，不得猜测或新增正式类型；在 `unresolved_components` 记录原始子任务，并标记 `component_mapping_status = COMPONENT_REVIEW_REQUIRED`。后续人工确认可通过新规则闭合该状态。 |
| `analysis_usage` | Historical Demand Pattern 可统计 `task_type_mode = MULTI_TASK` 的记录数，也可展开 `task_type_components` 统计各正式任务类型需求；不得将 `unresolved_components` 静默计入任何正式类型。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent、Data Gate、Historical Demand Pattern Agent |

### RULE-017 — MULTI_TASK 新增类型与补考组件映射

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-017 |
| `rule_name` | multi_task_manual_component_additions_and_resit_mapping |
| `scope` | task_type 值标准化、Data Quality、Data Gate、Historical Demand Pattern Agent |
| `business_definition` | 正式新增 `数据收集`、`降重`、`入学测试` 为 official task type（`source: manual_business_confirmation`，`status: ACTIVE`），并仅按下表更新指定 MULTI_TASK 组件。**该版本中“补考/补考作业 → 考试”的历史子规则已自 v11.0 起 DEPRECATED，由 RULE-021 替代。** |
| `official_canonical_list` | `config/dimensions/task_type/canonical.csv`：`数据收集`（`MANUAL-TASK-TYPE-004`）、`降重`（`MANUAL-TASK-TYPE-005`）、`入学测试`（`MANUAL-TASK-TYPE-006`）均为 ACTIVE 人工确认类型。 |
| `approved_multi_task_components` | `数据收集+分析` → [`数据收集`, `Analysis`]；`润色+降重+续写2000词` → [`润色-proofreading`, `降重`, `essay`]；`选课+入学测试` → [`选课`, `入学测试`]。 |
| `deprecated_historical_subrule` | `补考` / `补考作业` → `考试`；`补考+毕业论文` → [`考试`, `Dissertation`]；`补考作业+考试` → [`考试`]。`status: DEPRECATED`，`superseded_by: RULE-021`。仅为历史追溯，任何当前执行不得使用。 |
| `restriction` | 本规则仅覆盖列明的新增类型与非补考组件映射；不得据此对未确认的新值、其他支付文本或其他补考场景扩展推断。RULE-014 继续生效：`学年包` 与 `辅导年包` 不得归并。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent、Data Gate、Historical Demand Pattern Agent |

### RULE-018 — PROPOSED_MEDIUM 最终人工确认与单任务 Alias

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-018 |
| `rule_name` | proposed_medium_final_manual_task_type_aliases |
| `scope` | task_type 值标准化、Data Quality、Data Gate、Historical Demand Pattern Agent |
| `business_definition` | RUN-202608-DEMAND-001 的 41 个 Single Task `PROPOSED_MEDIUM` 原始值均完成最终人工审核，并按 `config/dimensions/task_type/active_aliases.yaml` 的逐值字典标准化。该字典是本规则的唯一机器可读 alias 清单；仅列明值可应用，禁止扩展推断。 |
| `special_corrections` | `大论文辅导` → `毕业论文辅导`（不得映射为 `Dissertation`）；`作业` → `作业`；`期末作业` → `作业`；`小组作业` → `小组作业`（独立类型，不得归并为 `作业` 或 `assignment`）。 |
| `added_official_task_types` | `毕业论文辅导`（`MANUAL-TASK-TYPE-007`）、`作业`（`MANUAL-TASK-TYPE-008`）、`小组作业`（`MANUAL-TASK-TYPE-009`）；均 `source: manual_business_confirmation`、`status: ACTIVE`。 |
| `restriction` | 本规则不处理任何 `REVIEW_REQUIRED` 原始值；不得将未列入 `active_aliases.yaml` 的新值自动映射为上述类型。RULE-014 继续生效：`学年包` 与 `辅导年包` 不得归并。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent、Data Gate、Historical Demand Pattern Agent |

### RULE-019 — Dissertation Proofreading Classification

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-019 |
| `rule_name` | dissertation_proofreading_classification |
| `scope` | task_type 单任务分类、Data Quality、Data Gate、Historical Demand Pattern Agent |
| `business_definition` | 正式新增 `毕业论文润色`（`MANUAL-TASK-TYPE-010`）为 official task type。润色类分类优先级固定为：明确毕业论文/大论文语义 > 可解析词数大于 10000 > 普通润色。 |
| `explicit_semantics` | 原始值明确含 `大论文润色`、`毕业论文润色` 或 `Dissertation润色` → `毕业论文润色`。 |
| `word_count_rule` | 原始值属于明确润色服务且可解析 `word_count > 10000` → `毕业论文润色`；**等于 10000 不适用**此规则。 |
| `ordinary_proofreading` | 其他润色类 → `润色-proofreading`，除非另有更具体的 ACTIVE Business Rule。 |
| `machine_rule_file` | `config/dimensions/task_type/classification_rules.yaml` 与 `config/data/standardization_rules.yaml` 的 RULE-019 条目。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent、Data Gate、Historical Demand Pattern Agent |

### RULE-020 — 剩余 Risk High-Confidence 最终人工确认

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-020 |
| `rule_name` | remaining_risk_high_confidence_task_type_aliases |
| `scope` | task_type 单任务标准化、Data Quality、Data Gate、Historical Demand Pattern Agent |
| `business_definition` | 以下 9 个风险候选已完成最终人工确认，必须按逐值映射处理：`毕业论文`、`毕业论文全包`、`毕业论文半包` → `Dissertation`；`Matlab代码作业`、`神经系统代码`、`编程代码` → `code/experiment`；`assignment` → `assignment`；`project` → `project`；`考试` → `考试`。 |
| `machine_rule_file` | `config/dimensions/task_type/risk_high_confirmed_aliases.yaml`。仅列明 raw value 可应用，禁止泛化。 |
| `restriction` | 本规则不处理任何 `REVIEW_REQUIRED` 原始值；不新增 official task type。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent、Data Gate、Historical Demand Pattern Agent |

### RULE-021 — 补考独立 Official Task Type

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-021 |
| `rule_name` | resit_is_independent_official_task_type |
| `scope` | task_type 单任务标准化、MULTI_TASK 组件标准化、Data Quality、Data Gate、Historical Demand Pattern Agent |
| `business_definition` | 正式新增 `补考`（`MANUAL-TASK-TYPE-011`）为独立 official task type。`补考`、`补考作业`及其明确补考变体均 → `补考`；词数、时长、`essay`、`辅导`等修饰信息不改变核心业务类型。`补考` 与 `考试` 是两个独立类型，禁止互相归并。明确「重写」值由更具体的 RULE-022 管理。 |
| `approved_single_task_aliases` | `补考`、`补考essay`、`2h补考`、`3h补考`、`补考辅导`、`2500词补考`、`3.5h补考`、`3H补考`、`essay补考`、`八小时补考`、`六小时补考`、`补考1500词`、`补考2h`、`补考6000词`、`补考90mins` → `补考`。 |
| `approved_multi_task_components` | `补考+毕业论文` → [`补考`, `Dissertation`]；`补考作业+考试` → [`补考`, `考试`]。两者不同，不得因去重规则删除其中任一组件。 |
| `deprecated_predecessor` | RULE-017 的“补考/补考作业 → 考试”子规则已 `DEPRECATED`，仅保留为历史版本追溯；当前所有执行以本规则为准。 |
| `machine_rule_file` | `config/dimensions/task_type/resit_aliases.yaml` 与 `config/data/standardization_rules.yaml` 的 RULE-021 条目。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent、Data Gate、Historical Demand Pattern Agent |

### RULE-022 — 重写归属补考业务

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-022 |
| `rule_name` | rewrite_is_resit_not_essay |
| `scope` | task_type 单任务标准化、Data Quality、Data Gate、Historical Demand Pattern Agent |
| `business_definition` | 在当前公司业务口径中，「重写」属于 `补考` 业务；它不是独立 official task type，亦不得按 `essay`、`ME` 或其他底层任务类型分类。词数、`essay`、`ME` 等修饰信息不改变该核心业务类型。 |
| `approved_single_task_aliases` | `2500词重写`、`essay重写`、`me重写` → `补考`。仅允许对 `config/dimensions/task_type/rewrite_aliases.yaml` 中列明的原始值直接应用，禁止向未确认的新值泛化。 |
| `deprecated_predecessor` | 历史 Round 1 中 `essay重写 → essay` 的候选判断已 `DEPRECATED / historical only`，由本规则取代；历史审计证据见 `task_type_round1_rewrite_assessment_deprecated.md`。 |
| `machine_rule_file` | `config/dimensions/task_type/rewrite_aliases.yaml` 与 `config/data/standardization_rules.yaml` 的 RULE-022 条目。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent、Data Gate、Historical Demand Pattern Agent |

### RULE-023 — 服务包／产品类已确认 Task Type Alias

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-023 |
| `rule_name` | service_package_product_task_type_aliases |
| `scope` | task_type 单任务标准化、Data Quality、Data Gate、Historical Demand Pattern Agent |
| `business_definition` | 以下服务包／产品原始值均按人工确认的业务实质映射。不得把 `SVIP`／`VIP` 保留为独立 official task type；`LR部分半包` 虽含 LR 语义，但当前以产品类型优先，映射为 `包课`。仅限逐值适用，禁止对新产品名或套餐名自行泛化。 |
| `approved_aliases` | `毕业无忧` → `毕业无忧`；`svip`、`SVIP`、`vip`、`VIP` → `预存`；`安心包`、`DP`、`卓越安心包`、`安心包三年` → `DP`；`半包`、`半包课`、`咨询包课`、`LR部分半包` → `包课`。 |
| `official_task_type` | `DP` 正式新增为独立 official task type（`MANUAL-TASK-TYPE-012`）；既有 `毕业无忧`、`预存`、`包课` 保持独立。 |
| `machine_rule_file` | `config/dimensions/task_type/service_package_aliases.yaml` 与 `config/data/standardization_rules.yaml` 的 RULE-023 条目。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent、Data Gate、Historical Demand Pattern Agent |

### RULE-024 — 质检类已确认 Task Type Alias

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-024 |
| `rule_name` | quality_inspection_task_type_aliases |
| `scope` | task_type 单任务标准化、Data Quality、Data Gate、Historical Demand Pattern Agent |
| `business_definition` | `质检` 为独立 official task type。当前历史业务口径不区分高级质检／普通质检；不得根据原始备注出现的“普通质检”等字样再拆级。毕业论文语义亦不改变此分类。 |
| `approved_aliases` | `质检`、`毕业论文质检`、`论文质检` → `质检`。 |
| `official_task_type` | 正式新增 `质检` 为独立 official task type（`MANUAL-TASK-TYPE-013`）。既有公司官方范围中的 `高级质检`、`普通质检` 保留为原始官方枚举，不删除、不覆盖；但本规则列明的历史原始值不得映射到它们。 |
| `machine_rule_file` | `config/dimensions/task_type/quality_inspection_aliases.yaml` 与 `config/data/standardization_rules.yaml` 的 RULE-024 条目。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent、Data Gate、Historical Demand Pattern Agent |

### RULE-025 — 毕业论文局部／阶段性服务产品口径

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-025 |
| `rule_name` | dissertation_partial_package_product_classification |
| `scope` | task_type 单任务标准化、Data Quality、Data Gate、Historical Demand Pattern Agent |
| `business_definition` | 本规则列明的原始值均属于毕业论文局部／阶段性服务，统一归入 `毕业论文半包`。业务产品口径优先于 LR、ME、文献综述、局部修改／润色、答辩 PPT 等文本表面任务语义，不得再按关键词拆分为其他 official task type。 |
| `approved_aliases` | `文献综述部分`、`2000词lr`、`5w词论文`、`LR修改`、`ME`、`ME部分`、`lr`、`me`、`文献综述`、`毕业论文400词`、`毕业论文浅润`、`毕业论文答辩PPT` → `毕业论文半包`。 |
| `official_task_type` | 正式新增 `毕业论文半包` 为独立 official task type（`MANUAL-TASK-TYPE-014`）。 |
| `machine_rule_file` | `config/dimensions/task_type/dissertation_partial_package_aliases.yaml` 与 `config/data/standardization_rules.yaml` 的 RULE-025 条目。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent、Data Gate、Historical Demand Pattern Agent |

### RULE-026 — 当前历史纯字数值归属 Essay

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-026 |
| `rule_name` | historical_pure_word_count_to_essay |
| `scope` | RUN-202608-DEMAND-001 的 task_type 单任务标准化、Data Quality、Data Gate、Historical Demand Pattern Agent |
| `business_definition` | 当前历史数据中，原始 task_type 仅包含明确字数／词数表达且没有任何明确任务语义时，统一映射为 `essay`。这是当前历史业务口径，不得无限泛化至未来未知文本。 |
| `priority_order` | 明确任务语义 > 特殊业务规则 > 纯字数 → `essay`。例如 `3000词方法论`、`1200词反思`、`1500词report` 含明确任务语义，必须优先按该语义及其他适用 ACTIVE 规则处理，不得仅按字数映射为 `essay`。 |
| `approved_aliases` | `150词`、`1200词`、`2000词`、`3000词`、`1000词`、`1100词`、`1200-1500词`、`1500词`、`1700词`、`200词`、`300词`、`3k词`、`4000词`、`4500`、`600词`、`750词`、`900词`、`三千词` → `essay`。 |
| `machine_rule_file` | `config/dimensions/task_type/pure_word_count_essay_aliases.yaml` 与 `config/data/standardization_rules.yaml` 的 RULE-026 条目。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent、Data Gate、Historical Demand Pattern Agent |

### RULE-027 — F组精确映射与 Task Type 分析排除

| 字段 | 值 |
|---|---|
| `rule_id` | RULE-027 |
| `rule_name` | final_other_task_type_aliases_and_task_type_only_exclusions |
| `scope` | RUN-202608-DEMAND-001 的 task_type 标准化、Data Quality、Data Gate、Historical Demand Pattern Agent |
| `approved_aliases` | `quiz` → `quiz`；`毕业设计辅导`、`毕设辅导` → `辅导`；`800词反思`、`地理作业1500词` → `essay`。新增 independent official task type：`quiz`（`MANUAL-TASK-TYPE-015`）及 `辅导`（`MANUAL-TASK-TYPE-016`）。 |
| `task_type_only_exclusions` | `2h高级财务`、`3000词方法论`、`3题`、`unity`、`两个小作业`、`写一个升学的kit`、`帮忙收集数据`、`总结`、`毕业影集`、`深润2000词`、`画图`、`续写`、`网站制作`、`计算机科学`、`选课课程内容分析`、`采访稿`、`重修`、`面试`、`题目` 标记 `EXCLUDED_BY_BUSINESS_RULE`。它们不进入本项目 task_type 聚合及趋势分析，但原始记录、`task_type_original`、来源追溯和学校／日期／金额／渠道等所有其他维度必须保留可用。 |
| `restriction` | 排除不是删除记录，也不是删除或改写原始 Excel；本规则仅针对列明原始值，禁止泛化。 |
| `machine_rule_file` | `config/dimensions/task_type/final_other_confirmed_aliases.yaml`、`config/dimensions/task_type/final_other_task_type_exclusions.yaml` 与 `config/data/standardization_rules.yaml` 的 RULE-027 条目。 |
| `source` | `manual_business_confirmation` |
| `status` | `ACTIVE` |
| `created_at` | 2026-08-20 |
| `affected_agents` | Data Standardization Agent、Data Quality Agent、Data Gate、Historical Demand Pattern Agent |

---

## 二、规则与 Agent 的对应关系

| Agent | 必须读取的规则（`affected_agents` 命中） |
|---|---|
| Data Intake Agent | 无当前 ACTIVE 规则直接适用于其职责范围（结构扫描不涉及业务语义/值处理），但**仍须将 `policies/business_rules.md` 列为 Required Input**，以便在扫描中若发现与规则假设冲突的结构性证据时能够识别并上报（例如：发现某字段的空值模式与 RULE-001 的"整行空白"定义存在歧义边界情况） |
| Schema Mapping Agent | RULE-007、RULE-008、RULE-009、RULE-010、RULE-011、RULE-012（字段级分类/排除/映射归属，不含值级计算） |
| Data Standardization Agent | RULE-001～006、RULE-009～027（含学校 alias 标准化、非学校值分类、国家冲突标记，以及已确认 task_type 独立值、指定 alias、MULTI_TASK 组件、润色、补考、重写、服务包、质检、毕业论文半包、纯字数分类及 task_type-only 排除） |
| Data Quality Agent | RULE-001、RULE-006、RULE-009、RULE-010、RULE-012、RULE-013、RULE-014～RULE-027（核实汇率、学历枚举、学校 alias/非学校分类、国家冲突标记、多任务组件、润色、补考、重写、服务包、质检、毕业论文半包、纯字数分类及 task_type-only 排除） |
| Data Gate | RULE-001、RULE-006、RULE-009、RULE-010、RULE-011、RULE-013、RULE-014～RULE-027（核实学校字典被正确应用，非学校值未进入排名，国家冲突未被静默改写，且 task_type alias/多任务组件/润色、补考、重写、服务包、质检、毕业论文半包、纯字数分类及 task_type-only 排除被正确应用） |
| Historical Demand Pattern Agent | RULE-011、RULE-013、RULE-014～RULE-027（不使用排除字段；学校排名仅使用真实 canonical school，不使用 `NON_SCHOOL`/`UNKNOWN`；区分学年包和辅导年包，按已确认 alias 汇总任务类型，可展开多任务组件；RULE-027 排除值不得进入 task_type 趋势分析） |

---

## 三、规则优先级

在任何 Agent 的判断链条中，优先级固定为：

```
人工确认的 ACTIVE Business Rule（本文件 + YAML）
        >
项目默认规则（docs/、orchestration/、policies/ 下的通用架构规则）
        >
Agent 模型推理（Agent 基于当前数据自行做出的语义判断）
```

- 若某个场景已有 `status: ACTIVE` 的人工确认规则覆盖，Agent **必须直接应用该规则**，不得重新论证、不得用自己的推理"优化"或"纠正"该规则的结论，即使 Agent 认为自己的判断更合理。
- 项目默认规则（如 Evidence First、Source Policy 中定义的通用要求）在没有更具体的人工确认规则时生效；一旦某个具体场景被人工规则覆盖，人工规则优先。
- Agent 自身的模型推理只能填补人工规则与项目默认规则都未覆盖的空白，且填补结果必须显式标注为 Agent 自身判断（而非包装成"已确认规则"），并在证据不充分时遵循 `UNKNOWN`/`INSUFFICIENT_EVIDENCE` 标记规则（见 [`policies/EVIDENCE_FIRST.md`](EVIDENCE_FIRST.md)）。

**任何 Agent 不得重新推翻 `status: ACTIVE` 且 `source: manual_business_confirmation` 的规则。** 推翻/修改规则只能通过人工更新本文件与 YAML 文件、并履行第七节的版本升级流程来完成。

---

## 四、Required Input 声明

自本版本起，以下 Agent 的 Contract（`agents/*.md`）中新增 **Required Shared Rules** 字段，明确声明：

- `policies/business_rules.md`（人类可读真源，全部相关 Agent 必读）
- `config/data/standardization_rules.yaml`（机器可读版本，凡涉及机器执行标准化的 Agent 必读）

具体见各 Agent Contract 与 [`docs/AGENT_CONTRACT.md`](../docs/AGENT_CONTRACT.md)。

---

## 五、`BUSINESS_RULE_CONFLICT` 处理流程

当 Agent 在真实数据中遇到以下情况之一：

1. 数据形态不落入任何 `ACTIVE` 规则的适用模式（如日期格式既不是 `M.D`、`M.D+附加文本`、`M月份`，也不是 `M.D1-M.D2` 区间）；
2. 数据与某条 `ACTIVE` 规则的前提假设相矛盾（如某条记录声称"整行空白"但实际有隐藏的非常规空值表示需要人工界定是否算空）；
3. 某个已确认规则字面上适用，但应用后产生明显不合理的结果，怀疑规则本身可能有遗漏场景；

Agent **必须**：

- **不得**自行修改 `policies/business_rules.md` 或 `config/data/standardization_rules.yaml`；
- **不得**臆测一个"看起来合理"的处理方式并静默套用；
- **必须**在对应 Artifact 的 `unresolved` 列表中输出一条 `status: "BUSINESS_RULE_CONFLICT"` 的记录，包含：冲突涉及的 `rule_id`（如有）、具体数据证据（字段、值、来源 `source_id`）、冲突原因说明；
- 将该记录同步交由 Knowledge Agent 记录（见第六节），等待人工确认后升级规则版本或给出临时处理指示。

`BUSINESS_RULE_CONFLICT` 与既有的 `UNKNOWN`/`INSUFFICIENT_EVIDENCE` 标记同属"无法自行下结论时的诚实标注"范畴，但语义更具体：前者特指"存在规则，但当前数据不服从/不匹配该规则"，后者泛指"证据不足，无法判断"。两者都不得被 Agent 自行"消化"为一个看似合理的默认处理。

单个 `BUSINESS_RULE_CONFLICT` 条目不必然导致 Agent 整体 `FAILED`——与 `UNKNOWN` 类似，Agent 仍可在如实标注该条目后继续 `COMPLETED`；但下游 Gate 在判定时必须能读到这些标记，并按各 Gate 自身的 Decision Rule Table 决定是否允许放行（通常：若冲突落在预测目标月份等关键范围内，应比照"目标月份数据问题"的收紧原则处理，不得 `CONDITIONAL`）。

---

## 六、变更记录（Changelog）

| 版本 | 日期 | 变更内容 |
|---|---|---|
| 1.0 | 2026-08-20 | 初始版本，登记 RULE-001～RULE-008（原第二版对话中临时登记的 `policies/confirmed_business_rules.json` 已被本文件与 YAML 文件正式取代，规则编号重新分配，详见该文件内的迁移说明） |
| 2.0 | 2026-08-20 | 新增 RULE-009（澳币金额换算人民币，固定汇率 4.5）、RULE-010（人民币金额字段归一）、RULE-011（客户备注/跟进反馈/未成交原因排除出分析 Schema，新增 `EXCLUDED_BY_BUSINESS_RULE` 状态）、RULE-012（学历大一～大四归一为「本科」，字段更名为 `degree_level`）。RULE-009/010 使此前 `REVIEW_REQUIRED` 的 `amount` 相关字段转为 `CONFIRMED`。同步更新 `agents/schema_mapping.md`、`agents/data_standardization.md`、`agents/data_quality.md`、`docs/AGENT_CONTRACT.md`、`gates/DATA_GATE.md`、`artifacts/README.md`，并重新生成 `runs/RUN-202608-DEMAND-001/artifacts/schema_mapping.json`。 |
| 3.0 | 2026-08-20 | 新增 RULE-013（学校实体标准化与国家一致性标记），建立人工确认字典 `config/data/school_aliases.yaml`：23 个 canonical 学校、47 个 approved 原始 alias；`/` 与 `未知` 分别作为 `NON_SCHOOL` / `UNKNOWN`，不参与学校排名。新增 `COUNTRY_SCHOOL_CONFLICT` 标记机制，不修改 country 原值。 |
| 4.0 | 2026-08-20 | 新增 RULE-014：人工确认 `学年包` 为独立正式订单类型，新增至 `config/dimensions/task_type/canonical.csv`（`MANUAL-TASK-TYPE-001`）；保留既有 `辅导年包`，两者禁止互相归并。原始公司订单类型 Excel 未修改。 |
| 5.0 | 2026-08-20 | 新增 RULE-015：人工确认 6 个含支付动作文本的 task_type alias，按业务实质映射至 `预存`、`包课`、`学年包`、`毕业无忧`；新增 `预存`、`毕业无忧` 为正式类型。`/` 与原始空值保留为唯一 UNKNOWN，禁止推测。 |
| 6.0 | 2026-08-20 | 新增 RULE-016：MULTI_TASK 不得压缩为单一类型，保留原始值、模式与正式组件列表；对无官方类型或无唯一规则的组件保留 `unresolved_components` 并要求人工确认，不自行新增正式类型。 |
| 7.0 | 2026-08-20 | 新增 RULE-017：人工确认新增 `数据收集`、`降重`、`入学测试` 为 official task type；闭合相应 MULTI_TASK 组件。其当时的“补考/补考作业 → 考试”子规则已在 v11.0 标记为 **DEPRECATED / historical only**，由 RULE-021 取代。 |
| 8.0 | 2026-08-20 | 新增 RULE-018：41 个 Single Task PROPOSED_MEDIUM 最终人工确认。新增 `毕业论文辅导`、`作业`、`小组作业` 为 official task type；`大论文辅导` 改映射为 `毕业论文辅导`，`期末作业` 映射为 `作业`，小组作业独立保留。 |
| 9.0 | 2026-08-20 | 新增 RULE-019：新增 official task type `毕业论文润色`；润色类按明确毕业论文语义、词数大于 10000、普通润色的优先级分类。仅更新当前风险候选的建议类型，其他风险项不自动批准。 |
| 10.0 | 2026-08-20 | 新增 RULE-020：人工确认剩余 9 条 Risk High-Confidence 单任务映射；不新增 official task type，不处理 REVIEW_REQUIRED。 |
| 11.0 | 2026-08-20 | 新增 RULE-021：`补考` 成为独立 official task type。废止 RULE-017 中“补考/补考作业 → 考试”的子规则；18 个单任务补考/重写变体及 2 条 MULTI_TASK 组件改映射为 `补考`。 |
| 12.0 | 2026-08-20 | 新增 RULE-022：人工确认 `重写` 在当前公司业务口径中属于 `补考`，不是独立类型，也不按 `essay`/`ME` 底层任务分类。`2500词重写`、`essay重写`、`me重写` → `补考`；历史 Round 1 的 `essay重写 → essay` 候选判断标记为 **DEPRECATED / historical only**。 |
| 13.0 | 2026-08-20 | 新增 RULE-023：完成 B 组服务包／产品类 13 个原始值审核。新增独立 official task type `DP`；`SVIP`/`VIP` 归入 `预存`，安心包类归入 `DP`，半包／包课类归入 `包课`，`毕业无忧` 保持映射至同名 official task type。 |
| 14.0 | 2026-08-20 | 新增 RULE-024：完成 C 组质检类 3 个原始值审核，新增独立 official task type `质检`。`质检`、`毕业论文质检`、`论文质检` 统一映射为 `质检`；不按高级／普通或论文语义拆级。 |
| 15.0 | 2026-08-20 | 新增 RULE-025：完成 D 组论文部分／缩写类 12 个原始值审核，新增独立 official task type `毕业论文半包`。列明的 LR、ME、文献综述、局部服务与答辩 PPT 值均按毕业论文局部／阶段性产品服务口径归入该类型。 |
| 16.0 | 2026-08-20 | 新增 RULE-026：完成 E 组仅字数／信息不足类 18 个原始值审核。当前历史中无明确任务语义的纯字数值映射为 `essay`；明确任务语义和特殊业务规则优先，禁止向未来未知文本无限泛化。 |
| 17.0 | 2026-08-20 | 新增 RULE-027：完成 F 组审核。`quiz`、毕业设计辅导／毕设辅导、反思／地理作业值按人工确认映射；其余 19 个无法唯一判断值仅排除出 task_type 聚合和趋势分析，记录及其他维度保留。 |

后续任何规则新增/修改，必须：新增一行变更记录；同步升级 `Business Rules Version` 与 YAML 的 `rules_version`；保留旧版本规则内容（不得直接覆盖删除），以便追溯"某个历史结论当时依据的是哪个版本的规则"。
