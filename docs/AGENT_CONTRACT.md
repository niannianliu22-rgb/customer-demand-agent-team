# AGENT_CONTRACT — Agent 间通信契约

> 核心规则：**Agent 之间不传自由散文，只传结构化 Artifact。** 一个 Agent 说"我认为需求会上升"不构成契约；一个附带来源、计算方法、数据行引用的结构化条目才构成契约。

## 1. 为什么禁止自由散文

自由散文无法被下游 Agent、Critic 或 Supervisor 程序化核验，只能被"相信"。这违反 Evidence First 原则（见 [`policies/EVIDENCE_FIRST.md`](../policies/EVIDENCE_FIRST.md)）。结构化 Artifact 才能被 Gate 机制自动核验、被 Critic Agent 逐条核实证据链、被 Knowledge Agent 准确记录、被人工审计者事后重放。

## 2. Artifact 的最低必备结构（信封）

任何一个 Agent 产出的 Artifact，无论具体业务字段如何，都必须包含以下公共信封（envelope）字段：

| 字段 | 说明 |
|---|---|
| `run_id` | 本 Artifact 所属的运行标识（见第 6 节 Run 隔离）。**本版本新增，必填**。 |
| `agent` | 产出该 Artifact 的 Agent 名称 |
| `wave` | 产出时所处的 Wave |
| `version` | 版本号，从 1 开始；返工后递增，不覆盖旧版本 |
| `generated_at` | 生成时间戳 |
| `inputs` | 本次运行读取的上游 Artifact 列表（含各自的 `run_id`、`version`——`run_id` 理论上应与本 Artifact 一致，见第 6 节的跨运行禁令） |
| `status` | `COMPLETED` / `FAILED` / `PARTIAL` |
| `items` | 业务内容主体，数组形式，每个元素对应一条可独立核验的结论/数据点，且每个元素带唯一 `id`（供 Gate/Critic 引用） |
| `evidence_refs` | 支撑 `items` 的证据引用列表（数据行范围、来源 URL、上游 Artifact 中的具体条目 ID） |
| `unresolved` | 无法确定、需标记为 `UNKNOWN` / `INSUFFICIENT_EVIDENCE` 的条目列表及原因 |

`items` 数组中的每一条业务结论，必须能通过 `evidence_refs` 回指到以下四类证据之一：具体的历史数据行范围；具体的官方来源（URL + 获取时间）；上游某个 Artifact 中带 ID 的具体条目；**或第 10 节定义的人工确认业务规则（`manual_business_confirmation`）**。**不允许**出现"根据历史经验""市场普遍认为"这类无法回指到 `evidence_refs` 的表述。

## 3. `unresolved` 是一等公民

任何 Agent 遇到无法验证、数据缺失、来源缺失的情况，必须显式写入 `unresolved`，标记为 `UNKNOWN`（含义或方向不明确）或 `INSUFFICIENT_EVIDENCE`（有部分线索但不足以下结论），不得省略、跳过或强行给出结论。下游、Critic、Gate 都必须读取并纳入判断。

## 4. 版本化与不可覆盖

- 任何 Artifact 在返工/重跑后，必须以新 `version` 落盘，不得覆盖旧版本文件；
- 建议命名：`insight_report.v1.json`、`insight_report.v2.json`；
- Critic 的 `critic_report.json` 必须明确对应它审核的是 `insight_report.json` 的哪个 `version`。

## 5. Gate 与 Critic 的职责边界（重要，本版本明确澄清）

系统中存在两种"把关"机制，二者性质、执行方式、判定内容完全不同，不得混淆：

| | **Gate**（Schema Gate / Data Gate / Insight Gate） | **Critic Agent** |
|---|---|---|
| 性质 | 独立、确定性、可审计的规则模块；**不是 Agent**，不占用 13 个 Agent 名额，也不拥有六状态机实例 | 13 个 Agent 之一，具备完整状态机实例 |
| 检查内容 | 结构性、完整性、硬条件验收——Artifact 是否完整、结构是否合规、量化指标是否达标、声称的证据是否真实存在 | 业务推理层面的反方质疑——某条洞察在业务逻辑上是否站得住、证据是否真正支撑其结论方向 |
| 判定依据 | 预先写死的 Decision Rule Table（见各 [`gates/`](../gates/) 文件），逐条命中规则，不即兴判断 | 逐条业务推理，允许基于证据链进行判断性质疑（但判断本身仍须落到 `PASS`/`REJECT` 并附 `reason`） |
| 读取范围 | **必须直接读取真实 Artifact**（如统一数据集本身、Data Intake Agent 产出的 `source_profiles`——本身是确定性工具 `inspect_excel.py` 的扫描结果，而非任何 Agent 的自然语言自述），不得只读上游 Agent 的摘要文字 | 读取 `insight_report.json` 及其引用的上游 Artifact，核实证据引用是否真实支撑结论 |
| 判定结果 | `PASS` / `CONDITIONAL` / `REJECT` / `HUMAN_REVIEW_REQUIRED`（四选一，按规则表自动得出） | `PASS` / `REJECT`（逐条 + 整体） |
| 放行权 | 由 Supervisor 原样执行判定结果，Supervisor 无权自行修改 Gate 结论 | Critic 的 `PASS` 是 Insight Gate 判定的输入之一，但 Insight Gate 本身仍会做结构性复核（见 [`gates/INSIGHT_GATE.md`](../gates/INSIGHT_GATE.md)），不是"Critic PASS 即自动放行"的单纯直通 |

简言之：**Critic 争论"对不对"，Gate 核验"全不全、真不真、够不够格"**。Insight Gate 不重新评判洞察的业务对错，那是 Critic 的职责范围。

Schema Gate 的每次正式执行必须产出 `runs/{run_id}/artifacts/schema_gate_result.json`，其结构由 [`gates/SCHEMA_GATE.md`](../gates/SCHEMA_GATE.md) 第 7 节固定。Data Standardization 只能消费该结果为 `PASS`，或为该 Gate Decision Rule Table 明确允许下游继续的 `CONDITIONAL`；不得仅凭 Schema Mapping Agent `COMPLETED` 状态或摘要启动。

## 6. Run 隔离（run_id）

- 系统的每一次完整运行（从 Schema Mapping 到 Action Agent）对应一个唯一的 `run_id`。
- 全部运行时 Artifact、日志、状态、最终输出必须隔离到：

```
runs/{run_id}/
  input/       — 本次运行使用的原始输入快照/指针（如目标预测年月参数、原始数据来源指针）
  artifacts/   — 本次运行产生的全部结构化 Artifact（schema_mapping.json 等中间产物）
  logs/        — 本次运行的 run_log.md 及其他日志
  state/       — 本次运行中全部 Agent 的状态机快照/历史
  final/       — 本次运行的最终交付物（forecast_report.json、action_plan.md）
```

- 全部 Agent Contract（信封结构，见第 2 节）必须携带 `run_id` 字段。
- **Agent 不得读取其他 `run_id` 的数据**，除非未来另有明确定义的跨运行知识调用机制（本版本不定义此机制）。
- 第一版（本阶段）仅要求一次运行处理一个预测目标月份，不实现并行执行；但架构本身（状态机、Supervisor 扫描/派发、Wave 进度、重扫）均以单一 `run_id` 为作用域设计，不假设"全局只有一次运行"，从而保证未来可以让多个 `run_id` 并行执行而互不干扰。

## 7. Critic 与 Demand Insight 之间的契约

- `insight_report.json` 的每个 `items[i]` 必须携带唯一 `id`；
- `critic_report.json` 的每个判定条目必须引用对应的 `id`，并给出 `verdict`（`PASS`/`REJECT`）与 `reason`；
- `REJECT` 的条目必须附 `issue_id`（用于返工计数，见 [`orchestration/ORCHESTRATOR_RULES.md`](../orchestration/ORCHESTRATOR_RULES.md) 第 5 节）与 `rework_instruction`。

## 8. Knowledge Agent 的契约特殊性

Knowledge Agent 不产出业务 Artifact，只产出 `run_log.md`（路径 `runs/{run_id}/logs/run_log.md`）。它对其他 Agent 的 Artifact 是**只读**关系——它读取信封字段（`run_id`/`agent`/`wave`/`version`/`status`/`generated_at`）与状态变化事件，不解读 `items` 的业务含义。返工事件的记录字段要求见 [`agents/knowledge.md`](../agents/knowledge.md)。

## 9. Artifact 命名与存放规范

见 [`artifacts/README.md`](../artifacts/README.md)。

### 9.1 标准数据产品发布契约

`runs/{run_id}/artifacts/` 是运行证据，不能被当成跨项目的稳定数据接口。只有在 Data Intake `COMPLETED`、Schema Mapping `COMPLETED`、Schema Gate `PASS`、Data Standardization `COMPLETED`、Data Quality `COMPLETED`、Data Gate `PASS` 全部满足后，确定性发布器才可从最终验收的 `unified_dataset.xlsx` 发布 stable 产品至 `data/processed/`。

- Data Gate `CONDITIONAL` 不满足 stable 条件，只可发布到 `data/processed/candidate/`，并在 metadata 标记 `release_status: "CONDITIONAL"` 与风险标记。
- Data Gate `REJECT` 或 `HUMAN_REVIEW_REQUIRED` 时不得发布任何 processed 产品。
- 发布副本必须携带数据集版本、规则版本、Gate 状态、质量指标、run 血缘、完整文件 checksum 和六个行级追溯字段（`source_id`、`source_file`、`source_sheet`、`source_row_id`、`year`、`department`）。
- 发布版不可覆盖；Business Rules、Schema、数据修正、来源或标准化口径变化均须递增产品版本。

发布器不是 Agent、无业务裁量权，且不得改写原始 Excel 或运行证据。完整发布包和 metadata 契约见 [`docs/DATA_PRODUCT_RELEASE.md`](DATA_PRODUCT_RELEASE.md)。

## 10. 人工确认业务规则（`manual_business_confirmation`）

某些结论无法从数据本身计算出来，也不存在官方渠道可查——它们是**人（业务负责人）就"这两个不同名称的字段是不是同一件事""这种格式的日期该怎么标准化"等问题做出的判断**。Evidence First 原则（"无来源，不下结论"）要求这类判断同样必须留痕、可追溯，而不能变成 Agent 私自决定或凭空默认的隐性假设。

不同 Agent 未来可能连接不同的底层模型，因此人工确认的业务规则**绝不能只存在于某一次对话的上下文中**——必须持久化为项目文件，成为相关 Agent 的 Required Input，任何模型、任何一次新对话都能读到同一份规则。

- **登记位置（本版本起为项目正式规则层，取代早期临时性的 `policies/confirmed_business_rules.json`——该文件现已标记 `deprecated: true` 并保留新旧规则编号的迁移映射，仅供追溯，不再作为规则来源读取）**：
  - [`policies/business_rules.md`](../policies/business_rules.md) — 人类可读 Single Source of Truth，含完整的 `rule_id`/`rule_name`/`scope`/`business_definition`/`examples`/`source`/`status`/`created_at`/`affected_agents`
  - [`config/data/standardization_rules.yaml`](../config/data/standardization_rules.yaml) — 机器可读版本，供 Agent/程序执行时读取，`rules_version` 必须与 `business_rules.md` 的 `Business Rules Version` 一致
  - 两者内容不一致本身即构成 `BUSINESS_RULE_CONFLICT`（见第 11 节），须立即人工核对修正
- **引用方式**：任何 Agent 的结论若依据某条已确认规则，必须在 `evidence_refs` 中显式引用其 `rule_id`（格式：`{"type": "manual_business_confirmation", "rule_id": "RULE-007"}`），不得只在自然语言描述中提及规则内容而不给出可核验的引用。
- **不是免检特权**：引用一条已确认规则，不代表可以跳过对当前具体数据的核实——例如 RULE-007 规定"客户来源=客户类型→channel"，Schema Mapping Agent 仍必须核实当前 source 中确实存在名为"客户来源"或"客户类型"的字段，才能应用该规则，不能对不存在该字段的 source 也套用。
- **与其他证据类型的关系**：作为"证据类型"，`manual_business_confirmation` 与"历史数据引用""官方来源引用""上游 Artifact 条目引用"并列，同属合法证据——它解决的是"计算和官方来源都无法回答，只能靠业务判断"的场景，而不是绕开计算/来源要求的捷径。凡是能通过数据或官方来源验证的结论，仍应优先使用那两类证据。但作为"权威等级"，一旦某条规则被登记为 `status: ACTIVE`，它在其 `scope` 覆盖的具体判断上，优先级高于 Agent 自身的模型推理，见第 11 节——这是两个不同维度，互不矛盾。
- **变更规则本身**：若某条已确认规则后续被证明不适用或需要修订，必须由人工显式更新 `business_rules.md` 与 `standardization_rules.yaml`（新增变更记录、升级版本号，不得静默覆盖旧规则内容），**任何 Agent 不得自行修改这两份文件**。
- **规则不止能决定"映射到什么"，也能决定"要不要纳入"**：例如 RULE-011 规定某些字段整体排除出分析 Schema——这类规则对应的产出状态是 `EXCLUDED_BY_BUSINESS_RULE`，与"尚不确定如何映射"的 `REVIEW_REQUIRED`、"无法判断"的 `UNMAPPED` 性质不同，三者（加上 `CONFIRMED`）共同构成 Schema Mapping 类 Artifact 的完整状态枚举，具体定义见 [`artifacts/README.md`](../artifacts/README.md) 与 [`agents/schema_mapping.md`](../agents/schema_mapping.md)。截至最新版本（Business Rules Version 2.0），已登记 RULE-001～RULE-012。

## 11. 业务规则优先级与 `BUSINESS_RULE_CONFLICT`

Agent 做出判断时，证据/规则来源的优先级固定为：

```
人工确认的 ACTIVE Business Rule（policies/business_rules.md + config/data/standardization_rules.yaml）
        >
项目默认规则（docs/、orchestration/、policies/ 下的通用架构规则，如 Evidence First、Source Policy）
        >
Agent 模型推理（Agent 基于当前数据自行做出的语义判断）
```

任何 Agent **不得重新推翻**已登记为 `status: ACTIVE` 且 `source: manual_business_confirmation` 的规则——不允许因为"我认为这样更合理"而偏离规则结论。

当真实数据与某条 `ACTIVE` 规则发生冲突（数据形态不落入规则的适用模式，或与规则的前提假设相矛盾）时，Agent：

- **不得**自行修改规则文件；
- **不得**臆测一个"看起来合理"的处理方式并静默套用；
- **必须**在对应 Artifact 的 `unresolved` 中输出一条 `status: "BUSINESS_RULE_CONFLICT"` 的记录，引用涉及的 `rule_id`（如有）与具体数据证据；
- 该记录须同步交由 Knowledge Agent 记录（见 [`agents/knowledge.md`](../agents/knowledge.md)），等待人工确认。

完整规则清单、优先级说明与 `BUSINESS_RULE_CONFLICT` 处理流程的权威版本见 [`policies/business_rules.md`](../policies/business_rules.md) 第三、五节；本节只做跨 Agent 通用契约层面的重申，不重复维护具体规则内容。
