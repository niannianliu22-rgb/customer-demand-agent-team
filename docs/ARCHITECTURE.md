# ARCHITECTURE — 客户需求分析 Agent Team

> 本文件定义系统的整体架构。本阶段仅搭建组织与机制，不实现业务逻辑、不写预测代码。

## 1. 架构目标

系统将两个销售部门、三年（2023 / 2024 / 2025）共 6 份历史咨询/订单表，转化为：

1. 一份可信、可追溯的统一历史数据集；
2. 一套基于历史同期规律 + 当年官方学业节点的需求洞察，且该洞察必须经过 Critic 质疑与审核；
3. 未来 7 / 14 / 28 天的重点需求预测；
4. 可执行的销售、运营、业务准备动作；
5. 一份完整、可审计的团队运行日志。

架构的第一原则是**可审计性**：任何一个业务结论，都必须能沿着 Artifact 链条回溯到原始数据行和官方来源，而不是依赖某个 Agent 的自我陈述。

## 2. 六层结构（治理层 + 5 个部门）

| Layer | 部门 | 职责范围 | Agent |
|---|---|---|---|
| L0 | 治理层 | 全流程调度、依赖管理、闸门执行、审计记录 | Supervisor, Knowledge |
| L1 | 数据治理部 | 数据登记、结构识别、标准化、质量审核 | Data Intake, Schema Mapping, Data Standardization, Data Quality |
| L2 | 历史与情报部 | 历史同期规律、当年官方学业节点 | Historical Demand Pattern, Academic Context |
| L3 | 验证与洞察部 | 判断历史规律今年是否适用、形成需求洞察 | Current Context Validation, Demand Insight |
| L4 | 质疑与预测部 | 质疑/驳回洞察、形成 7/14/28 天预测 | Critic, Forecast |
| L5 | 行动输出部 | 将预测转化为可执行动作 | Action |

共 **13 个 Agent**，不多不少（数据治理部固定为 Data Intake → Schema Mapping → Data Standardization → Data Quality 四个独立 Agent，职责逐级递进、不得合并）。**Gate（Schema Gate / Data Gate / Insight Gate）不是 Agent，不占用这 13 个名额**——它是独立、确定性、可审计的规则模块，详见第 4 节与 [`docs/AGENT_CONTRACT.md`](AGENT_CONTRACT.md) 第 5 节 Gate 与 Critic 的职责边界。

详见 [`AGENT_MAP.md`](AGENT_MAP.md)（逐 Agent 档案）与 [`AGENT_RESPONSIBILITY.md`](AGENT_RESPONSIBILITY.md)（责权边界）。

## 3. 六状态模型（本版本新增 `HUMAN_REVIEW_REQUIRED`）

每个 Agent 实例（在其所属 `run_id` 范围内）处于以下六种状态之一：

`BLOCKED` → `READY` → `RUNNING` → `COMPLETED` / `FAILED` / `HUMAN_REVIEW_REQUIRED`

- `BLOCKED`：依赖未满足，或上游处于 `FAILED`/`HUMAN_REVIEW_REQUIRED`，或前置 Gate 未放行；
- `READY`：全部依赖 `COMPLETED` 且上游 Artifact 可读，前置 Gate 已放行——唯一的运行许可来源；
- `RUNNING`：已被派发，正在执行；
- `COMPLETED`：已产出符合契约的 Artifact；
- `FAILED`：结构性障碍，完全无法产出；
- `HUMAN_REVIEW_REQUIRED`：同一问题（`issue_id`）累计 3 次判定未通过（1 次初始 + 2 次自动返工）、或 Gate 遇到规则未覆盖的情形，系统停止自动决策，等待人工介入。

Wave 只定义"最早可以运行的时点"，不授予运行许可；上游 `FAILED`/`HUMAN_REVIEW_REQUIRED`，下游必须保持/变为 `BLOCKED`。完整状态迁移见 [`orchestration/STATE_MACHINE.md`](../orchestration/STATE_MACHINE.md)。

## 4. 三道硬闸门（Hard Gates）：结构性判定，不做业务推理

| Gate | 位置 | 把关对象 |
|---|---|---|
| Schema Gate | Schema Mapping Agent 之后、Data Standardization Agent 之前 | 本次 run 的数据源登记是否完整、字段结构是否已被完整识别与映射（Gate 直接读取 Data Intake Agent 产出的 `source_manifest`/`source_profiles` 与 `schema_mapping.json` 比对，而非只读映射报告的文字结论） |
| Data Gate | Data Quality Agent 之后、Historical Demand Pattern Agent 之前 | 统一历史数据集是否达到可信标准（Gate 直接检查统一数据集、cleaning log、源数据溯源信息，而非只读质量报告文字结论） |
| Insight Gate | Critic Agent 判定之后、Forecast Agent 之前 | Critic 的审核过程是否完整、证据链是否可验证、来源政策是否合规（Gate 不重新评判洞察的业务对错——那是 Critic 的职责） |

每道 Gate 的判定结果为四选一：**`PASS` / `CONDITIONAL` / `REJECT` / `HUMAN_REVIEW_REQUIRED`**。每道 Gate 必须在自己的文件中预先写死 Decision Rule Table：允许 CONDITIONAL 的情形、允许放行到的下游、必须携带的风险标记、绝不能 CONDITIONAL 的情形（Never-Conditional）。**`CONDITIONAL` 不等于 `PASS`**——它只能沿预定义规则自动放行，且必须携带风险标记透传给下游；当前情况不被任何预定义规则覆盖时，Gate 输出 `HUMAN_REVIEW_REQUIRED`，不允许 Supervisor 凭主观判断代为归类。详见 [`gates/`](../gates/) 三份文件。

## 5. 返工上限与人工介入

同一问题（`issue_id`）最多允许 **2 次自动返工**：

| 判定序号 | 结果 | 状态迁移 |
|---|---|---|
| 第 1 次 REJECT | 未通过 | 责任 Agent `COMPLETED → READY`，自动返工 |
| 第 2 次 REJECT | 未通过 | 责任 Agent `COMPLETED → READY`，最后一次自动返工 |
| 第 3 次 REJECT | 仍未通过 | 停止自动返工，责任 Agent `COMPLETED → HUMAN_REVIEW_REQUIRED`，下游保持 `BLOCKED` |

此规则统一适用于 Schema Gate / Data Gate 触发的返工，以及 Critic ⇄ Demand Insight Agent 的返工循环，**禁止任何无限自动返工循环**。每一次返工，Knowledge Agent 必须记录 `issue_id`、`reject_reason`、`retry_count`、`responsible_agent`、`previous_artifact`、`revised_artifact`、`previous_conclusion`、`revised_conclusion` 七项，缺一不可。详见 [`orchestration/ORCHESTRATOR_RULES.md`](../orchestration/ORCHESTRATOR_RULES.md) 第 5 节。

## 6. Run 隔离（run_id）

系统的每一次完整运行对应唯一的 `run_id`，全部运行时 Artifact、日志、状态、最终输出隔离到 `runs/{run_id}/{input,artifacts,logs,state,final}/`。全部 Agent Contract 的信封结构携带 `run_id` 字段；Agent 不得读取其他 `run_id` 的数据。第一版仅支持单 `run_id` 顺序执行一个预测目标月份，但状态机、Supervisor 调度、Wave 进度、重扫机制均以单一 `run_id` 为作用域设计，为未来并行运行预留空间。详见 [`docs/AGENT_CONTRACT.md`](AGENT_CONTRACT.md) 第 6 节。

## 7. Evidence First（证据优先）

> **Agent 自述只算 metadata；Artifact 才算真实证据。**

"我完成了"不能作为完成依据。任何完成判定、Gate 判定、Critic 判定，都必须基于对真实 Artifact（文件、结构、数字、来源）的检查。本版本进一步要求：**Gate 必须直接读取真实 Artifact 进行检查**（如统一数据集本身、原始表结构），不允许只读取上游 Agent 的自述/摘要文字。详见 [`policies/EVIDENCE_FIRST.md`](../policies/EVIDENCE_FIRST.md)。

配套原则：无来源，不下结论（[`policies/SOURCE_POLICY.md`](../policies/SOURCE_POLICY.md)）；无计算，不判断；无法验证时必须标记 `UNKNOWN` / `INSUFFICIENT_EVIDENCE`。

## 8. Artifact 流转

Agent 之间不传自由散文，只传结构化 Artifact。完整的 Artifact 契约见 [`docs/AGENT_CONTRACT.md`](AGENT_CONTRACT.md)，命名规范见 [`artifacts/README.md`](../artifacts/README.md)。

Artifact 主链路（简化视图，完整流程见 [`docs/WORKFLOW.md`](WORKFLOW.md)）：

```
runs/{run_id}/input/  (本次run的原始Excel文件 + 预测目标年月参数)
   → [Data Intake Agent] → source_manifest.json + source_profiles/*.json
   → schema_mapping.json                [Schema Gate: PASS/CONDITIONAL/REJECT/HUMAN_REVIEW_REQUIRED]
   → standardization_rules.json + unified_dataset.xlsx
   → quality_report.json                [Data Gate: PASS/CONDITIONAL/REJECT/HUMAN_REVIEW_REQUIRED]
   → historical_pattern_report.json  ─┐
   → academic_context_report.json    ─┴→ validation_report.json
   → insight_report.json ⇄ critic_report.json (PASS/REJECT，最多2次自动返工) [Insight Gate]
   → forecast_report.json
   → action_plan.md   (runs/{run_id}/final/)

（贯穿全程）run_log.md ← Knowledge Agent 持续记录（runs/{run_id}/logs/）
```

## 9. 原始数据不可覆盖

原始 6 张历史表在整个流程中只读，任何标准化、清洗、合并操作都产生新的 Artifact，不得修改或覆盖原始文件。所有清洗规则记录在 `standardization_rules.json` 中，确保可追溯、可重放。

## 10. 本阶段范围声明

本阶段只完成：项目目录结构、组织文档、编排规则、闸门标准（含四态判定与 CONDITIONAL 规则表）、Agent 角色契约、返工上限机制、Run 隔离设计。

本阶段明确不做：Agent 业务 Prompt 的详细实现、Python 清洗/预测代码、与 Claude View / ClauDepot 的集成、PPT 产出、`runs/` 目录的实际创建（无真实运行发生）、多 `run_id` 并行调度的具体实现。
