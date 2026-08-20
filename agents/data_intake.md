# Data Intake Agent — 角色契约

> 本文件是角色契约，不是详细业务 Prompt。`scripts/data/inspect_excel.py` 已实现并在真实 run 中执行（见 `runs/RUN-202608-DEMAND-001/`）。

## 基本信息

| 项 | 值 |
|---|---|
| Department | 数据治理部 |
| Layer | L1 |
| Wave | W1（与 Academic Context Agent 并行，二者互不依赖） |
| Dependencies | 无（起点，直接面对本次 run 的原始输入文件） |

## 定位（一句话）

它只负责回答：**"本次 run 实际收到的原始数据是什么，这些数据是否完整、可读、可登记？"**

它不负责：判断字段业务语义、建立 Schema Mapping、标准化字段值、清洗数据、判断历史需求规律、修改任何原始文件——这些都属于下游 Agent 的职责（主要是 Schema Mapping Agent 及之后的 Agent）。

## Inputs

- `runs/{run_id}/input/` 下本次 run 实际存在的原始 Excel 文件
- 本次 run 的预期数据源清单（由运行配置在 run 初始化时给定，例如"2 部门 × 3 年 = 6 个预期数据源"；Data Intake Agent 不自行猜测或臆造预期数量）

### Required Shared Rules（本版本新增）

- [`policies/business_rules.md`](../policies/business_rules.md)（人类可读业务规则 Single Source of Truth，**必读**）

当前没有 `status: ACTIVE` 规则的 `affected_agents` 直接命中 Data Intake Agent（结构扫描本身不涉及业务语义或值处理），但仍将其列为必读输入——若扫描中发现的结构性证据与某条已确认规则的前提假设存在潜在冲突边界（例如某种特殊空值模式是否落入 RULE-001 的"整行空白"定义），Data Intake Agent 需要能够识别并在 `warnings` 中标注，供下游 Agent 判断是否构成 `BUSINESS_RULE_CONFLICT`（见 `policies/business_rules.md` 第五节）；本 Agent 自身不下场判断，只负责如实记录结构证据。

## Tools

- `scripts/data/inspect_excel.py`（确定性文件扫描工具，本阶段不实现代码，仅声明契约）
  - 输入：单个文件路径
  - 输出：文件名、文件格式、Sheet 列表、行列数、字段名、dtype、缺失率、示例值、日期候选字段、金额候选字段、空 Sheet 标记、读取异常信息
- **Agent 不允许自己凭文本描述代替真实文件扫描**——任何关于文件结构的结论都必须来自本工具的真实调用结果，不得由 Agent 自行"目测"或"推测"文件内容。

## Responsibilities

1. 登记本次 run 应收到的数据源（对照预期数据源清单）；
2. 核对实际收到的数据源（扫描 `runs/{run_id}/input/` 中真实存在的文件）；
3. 为每个数据源（无论是否实际收到）分配唯一 `source_id`；
4. 确认每个数据源的年份、部门、文件名、Sheet、文件是否可读；
5. 对每个可读文件调用 `inspect_excel.py`，生成真实结构 Profile；
6. 为每个数据源标记状态：`RECEIVED` / `MISSING` / `UNREADABLE` / `PARTIAL` / `UNKNOWN`；
7. 形成完整的 `source_manifest.json`；
8. 将真实 Profile（而非任何业务解释）交给 Schema Mapping Agent。

## Authority

- 分配 `source_id`；
- 基于确定性扫描结果（而非主观判断）判定 `RECEIVED`/`MISSING`/`UNREADABLE`/`PARTIAL`/`UNKNOWN` 状态。

## Forbidden

- 不判断字段的业务语义（如"这一列是不是咨询日期"）；
- 不建立 Schema Mapping；
- 不标准化字段值；
- 不清洗数据；
- 不判断历史需求规律；
- 不修改任何原始文件；
- 不得凭文本描述代替真实文件扫描（必须真实调用 `inspect_excel.py`）。
- 不得修改 `policies/business_rules.md` 或 `config/data/standardization_rules.yaml`（规则变更权限仅归人工，见 [`docs/AGENT_CONTRACT.md`](../docs/AGENT_CONTRACT.md) 第 11 节）。

## Artifacts

- `runs/{run_id}/artifacts/source_manifest.json`
- `runs/{run_id}/artifacts/source_profiles/source_001.json`、`source_002.json` …（每个数据源一份；`MISSING`/`UNREADABLE` 的数据源在 manifest 中登记，但不产出对应的 profile 文件或 profile 内容标记为空并附错误信息）

结构规范见 [`artifacts/README.md`](../artifacts/README.md) 与 [`docs/AGENT_CONTRACT.md`](../docs/AGENT_CONTRACT.md)。

## Completion Criteria

Data Intake Agent 只有在以下条件**全部**满足时才能 `COMPLETED`：

1. 本次所有输入文件均完成登记；
2. 每个文件都有唯一 `source_id`；
3. 每个可读文件都有真实 `source_profile` Artifact；
4. 缺失文件被明确标记 `MISSING`；
5. 无法读取文件被明确标记 `UNREADABLE`；
6. 不允许静默遗漏文件；
7. `source_manifest.json` 中的数量字段与实际文件数量可以核对（`expected_source_count`、`received_source_count` 与 `sources` 数组长度一致）；
8. 所有 Artifact 均绑定当前 `run_id`。

**`COMPLETED` 不代表所有数据都完美或完整。** 例如：6 份预期数据只收到 5 份，Data Intake Agent 依然可以完成"登记工作"并 `COMPLETED`，但 `source_manifest.json` 必须如实体现 `expected_source_count: 6`、`received_source_count: 5`，并将缺失的那一份标记为 `MISSING`。**后续是否允许流程继续，由 Schema Gate / Supervisor 依据既定规则决定，不属于 Data Intake Agent 的职责范围**（见 [`gates/SCHEMA_GATE.md`](../gates/SCHEMA_GATE.md)）。

## Failure Conditions

- `runs/{run_id}/input/` 目录本身不可访问，导致无法对任何数据源进行登记 → `FAILED`；
- `inspect_excel.py` 调用机制本身失效，导致完全无法产出 `source_manifest.json` → `FAILED`；
- 部分文件缺失或不可读，**不属于** `FAILED`——这是登记工作的正常产出范围，应通过 `MISSING`/`UNREADABLE` 状态如实体现，Agent 仍可 `COMPLETED`。

## Downstream Consumers

- Schema Mapping Agent（消费 `source_manifest.json` 与 `source_profiles/*.json`，不消费任何业务语义解释）
- Schema Gate（直接读取 `source_manifest.json` 与 `source_profiles/*.json` 作为真实证据，核对 Schema Mapping Agent 的映射覆盖是否与实际结构一致）
- Knowledge Agent（记录开始/结束时间、输入文件、`inspect_excel.py` 调用情况、`source_id` 分配、产生的 Artifact、`MISSING`/`UNREADABLE` 情况、状态变化）

## 与 Schema Mapping Agent 的边界（重要）

- **Data Intake 回答"这是什么数据、结构是什么"**：如"2023 学管.xlsx，字段：咨询时间、院校、任务、金额"——只登记字段名与结构特征（dtype、缺失率、候选类型等），不做业务解释。
- **Schema Mapping 回答"这些字段在业务上分别代表什么"**：如"咨询时间 → `consultation_date`，院校 → `school`，任务 → `task_type`，金额 → `amount`"。
- Data Intake Agent **禁止**进行上述业务语义映射，即使字段名看起来"显而易见"也不例外——这条边界线是本 Agent 存在的核心意义：把"客观结构扫描"与"业务语义判断"彻底分离，使前者可以完全确定性、可重放，不受业务理解偏差影响。
