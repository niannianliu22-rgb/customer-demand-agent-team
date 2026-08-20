# INSIGHT GATE

> 位置：Critic Agent 判定之后，Forecast Agent 之前。把关对象：需求洞察是否经受住质疑，是否可以作为预测依据。
>
> **Gate 的性质**：独立、确定性、可审计的规则模块，不是 Agent。判定结果为四选一：`PASS` / `CONDITIONAL` / `REJECT` / `HUMAN_REVIEW_REQUIRED`。Supervisor 只能原样执行，无权自行改判（见 [`orchestration/ORCHESTRATOR_RULES.md`](../orchestration/ORCHESTRATOR_RULES.md) 第 6、7 节）。
>
> **Gate 与 Critic 的边界（重要）**：Critic Agent 负责**业务推理层面的反方质疑**——即"这条洞察在业务逻辑上站不站得住"；Insight Gate 负责**结构性、完整性和硬条件验收**——即"Critic 的审核过程本身是否完整、其判定是否可核实、洞察的证据引用是否符合来源政策"。Insight Gate **不重新评判洞察的业务对错**，那是 Critic 的职责范围，两者不得混淆。

## Directly-Inspected Artifacts（Gate 必须直接读取的真实证据）

- `critic_report.json`（Critic 的判定结果，最新版本）
- `insight_report.json`（被审核的版本，用于核实 Critic 判定条目是否覆盖全部洞察条目——不采信 `critic_report.json` 自称"已全部审核"）
- 被引用的上游 Artifact（`historical_pattern_report.json`、`academic_context_report.json`、`validation_report.json`）——抽样核实 `insight_report.json` 中 `evidence_refs` 指向的条目在这些 Artifact 中确实存在，而不仅相信 Critic 报告中"证据已核实"的文字表述

## Check Items

1. **覆盖完整性**：`critic_report.json` 的判定条目是否逐一对应 `insight_report.json` 的全部 `items`，无遗漏。
2. **判定明确性**：每条判定是否为明确的 `PASS`/`REJECT`。
3. **REJECT 条目的可执行性**：每个 `REJECT` 是否附带 `reason` 与 `rework_instruction`，且带有稳定 `issue_id`。
4. **证据核实痕迹的可验证性**：抽样核实 `critic_report.json` 声称已核实的 `evidence_refs`，在对应上游 Artifact 中是否真实存在且内容匹配。
5. **来源政策符合性**：核实洞察引用的证据是否符合 [`policies/SOURCE_POLICY.md`](../policies/SOURCE_POLICY.md)（学业节点是否来自官方来源、历史数据是否为目标月份同期数据、近期走势是否被误用为主要依据）。
6. **信封结构**：`critic_report.json`、`insight_report.json` 是否符合契约结构，且携带正确、一致的 `run_id`。

## Decision Rule Table

| Rule ID | 触发条件 | 判定 | 允许继续到的下游 | 必须携带的风险标记 |
|---|---|---|---|---|
| IG-P1 | `insight_report.json` 全部 `items` 在 `critic_report.json` 中判定为 `PASS`；证据核实抽样通过；来源政策符合性核实通过 | `PASS` | Forecast Agent | 无 |
| IG-C1 | 全部关键洞察条目（直接支撑 7/14/28 天预测主结论的条目）均为 `PASS`；仅存在被标记为 `UNKNOWN`/`INSUFFICIENT_EVIDENCE`（而非 `REJECT`）的**非关键**洞察条目，且 Critic 已在报告中说明"不影响核心洞察" | `CONDITIONAL` | Forecast Agent | `risk_flag: INSIGHT_PARTIAL_UNCERTAINTY`，需列出具体条目 ID，Forecast Agent 须在对应预测窗口同步标注不确定性 |
| IG-R1 | 存在任一 `items` 条目被判定为 `REJECT` 且未重做通过 | `REJECT` | 无 | — |
| IG-R2 | `critic_report.json` 未覆盖全部洞察条目（判定不完整） | `REJECT` | 无 | — |
| IG-R3 | Gate 抽样核实发现 Critic 声称已核实的证据实际不存在或不匹配（审核本身不可信） | `REJECT`（视为该轮 Critic 审核无效，需 Critic 重新审核，`issue_id` 计入 Critic 返工计数） | 无 | — |
| IG-R4 | 来源政策符合性核实未通过（如引用了非官方学业节点、或将近期走势当作主要依据） | `REJECT` | 无 | — |

## Never-Conditional（绝不能 CONDITIONAL 的情形）

- 任何被 Critic 明确判定为 `REJECT` 的条目——`REJECT` 只能通过返工重做变为 `PASS`，不能被 Gate 用风险标记"绕过"；
- 直接支撑 7/14/28 天预测主结论的关键洞察条目存在 `UNKNOWN`/`INSUFFICIENT_EVIDENCE`——只能 `REJECT` 打回补充证据，不得放行；
- 来源政策不符合（非官方来源、近期走势被误用为主要依据）——这是硬性合规问题，不属于"可接受风险"。

## HUMAN_REVIEW_REQUIRED

若某洞察条目的"是否关键"存在争议、或 Critic 报告的证据核实痕迹模糊到无法通过抽样明确判定真伪，Gate 输出 `HUMAN_REVIEW_REQUIRED`，不得由 Supervisor 主观归类为 PASS/CONDITIONAL/REJECT 中的任一种。

## Downstream Impact

- **PASS / CONDITIONAL（按命中规则）**：Forecast Agent 的 Gate 依赖条件满足；`CONDITIONAL` 的风险标记需随链路透传，体现在 Forecast Agent 对应预测窗口的不确定性标注中。
- **REJECT**：Forecast Agent 保持 `BLOCKED`；Demand Insight Agent（或 IG-R3 情形下的 Critic Agent 本身）进入返工流程（`issue_id` 计数，最多 2 次自动返工，第 3 次未通过转 `HUMAN_REVIEW_REQUIRED`），形成 W6/W7 循环（见 [`docs/WORKFLOW.md`](../docs/WORKFLOW.md)）。
- **HUMAN_REVIEW_REQUIRED**：Forecast Agent 保持 `BLOCKED`；Critic Agent 与 Demand Insight Agent 状态维持各自 `COMPLETED`；等待人工补充判断或修订本 Gate 的规则表。
