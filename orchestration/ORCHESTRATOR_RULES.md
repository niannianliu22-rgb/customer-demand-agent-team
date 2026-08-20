# ORCHESTRATOR_RULES — Supervisor 编排规则

> 定义 Supervisor Agent 如何扫描、派发、处理依赖、处理失败、处理返工（含返工上限）、执行 Gate 结果、最终放行。Supervisor 不做业务判断——本文件全部规则都只涉及"流程能不能走"，不涉及"结论对不对"，也不涉及"要不要放宽标准"。

> **Run 范围声明**：本文件描述的全部扫描/派发/状态判定，均在单个 `run_id` 范围内进行（见 [`docs/AGENT_CONTRACT.md`](../docs/AGENT_CONTRACT.md) 的 Run 隔离章节）。第一版只支持单 `run_id` 顺序执行，但规则本身不得假设"全局只有一个运行"，须保证未来可在多个 `run_id` 间并行执行而不互相干扰。

## 1. 扫描（Scan）

- 扫描对象：当前 `run_id` 下全部 13 个 Agent 的当前状态（六状态，见 [`STATE_MACHINE.md`](STATE_MACHINE.md)）。
- 扫描时机：
  1. 流程启动时（初始化全部 Agent 为 `BLOCKED`，无依赖的 Agent 直接判定是否可转 `READY`）；
  2. 每次任一 Agent 变为 `COMPLETED`、`FAILED` 或 `HUMAN_REVIEW_REQUIRED` 后；
  3. 每个 Wave 结束后的强制重扫（见 [`RESCAN_RULES.md`](RESCAN_RULES.md)）；
  4. 每次 Gate 做出 `PASS`/`CONDITIONAL`/`REJECT`/`HUMAN_REVIEW_REQUIRED` 判定后；
  5. 每次 Critic 做出 `PASS`/`REJECT` 判定后；
  6. 每次人工介入将某 Agent 由 `HUMAN_REVIEW_REQUIRED` 迁移回 `READY`，或由 `FAILED` 迁移回 `BLOCKED` 后。
- 扫描内容：对每个非 `RUNNING`/`COMPLETED`（终态且未被打回）的 Agent，检查其全部依赖是否 `COMPLETED`，且对应上游 Artifact 是否可读。

## 2. 派发（Dispatch）

- 只有状态为 `READY` 的 Agent 可被派发进入 `RUNNING`。
- Wave 不是派发许可——即使某 Agent 所属 Wave 已到达，只要其状态不是 `READY`，就不得派发。
- 同一 Wave 内多个 `READY` Agent 之间无固定先后顺序，可并行派发。
- 派发动作本身必须被 Knowledge Agent 记录（时间、目标 Agent、`run_id`、依赖满足证据）。

## 3. 依赖处理

- 依赖关系是有向的，定义在 [`docs/AGENT_MAP.md`](../docs/AGENT_MAP.md) 的 `Dependencies` 字段中，Supervisor 不得自行增减依赖。
- 依赖判定标准：上游 Agent 状态为 `COMPLETED`，**且**其产出的 Artifact 实际可读（Evidence First——不采信状态字段本身）。
- 若依赖链条中存在 Gate，依赖判定还需附加"对应 Gate 判定为 `PASS`，或按其预定义规则表判定为 `CONDITIONAL` 并允许该下游继续"这一条件（见第 6 节、[`gates/`](../gates/) 三份文件）。

## 4. 失败与人工介入状态的处理

- 任一 Agent 状态变为 `FAILED` 或 `HUMAN_REVIEW_REQUIRED` 时，Supervisor 必须：
  1. 立即将全部直接依赖它的下游 Agent 状态设为/保持 `BLOCKED`（不得转 `READY`）；
  2. 沿依赖图向下传播，下游的下游同样保持 `BLOCKED`（见 [`policies/FAILURE_PROPAGATION.md`](../policies/FAILURE_PROPAGATION.md)，该传播原则同等适用于 `HUMAN_REVIEW_REQUIRED`）；
  3. 通知 Knowledge Agent 记录事件及传播影响范围；
  4. 不自动重试——`FAILED` 需人工确认根因已修复后迁移回 `BLOCKED`（重新走依赖判定）；`HUMAN_REVIEW_REQUIRED` 需人工明确授权后迁移回 `READY`（且 `retry_count` 重置为 0）。Supervisor 不得自行执行这两类迁移。

## 5. 返工处理与返工上限（Rework Handling & Retry Cap）

### 5.1 返工触发场景

仅限以下两类，均适用本节的返工上限规则：

1. Gate REJECT（Schema Gate / Data Gate）→ 打回产出对应 Artifact 的 Agent；
2. Critic REJECT（Insight Gate 前置）→ 打回 Demand Insight Agent。

### 5.2 `issue_id`：返工计数的最小单位

每一次 REJECT 判定必须附带一个稳定的 `issue_id`（由做出判定的 Gate 或 Critic 生成并保持跨轮次一致），用于标识"这是不是同一个问题在被反复拒绝"。不同 `issue_id` 的 REJECT 各自独立计数，不得合并——避免一个全新问题的首次 REJECT 被错误地计入另一个旧问题已经积累的返工次数。

`retry_count` 以 `(run_id, issue_id)` 为键维护，初始为 0。

### 5.3 返工上限规则（同一 `issue_id` 最多 2 次自动返工）

| 判定序号 | 结果 | Supervisor 动作 | `retry_count` 变化 |
|---|---|---|---|
| 第 1 次 REJECT | 未通过 | responsible_agent：`COMPLETED → READY`，触发自动返工 | 0 → 1 |
| 第 2 次 REJECT | 未通过 | responsible_agent：`COMPLETED → READY`，触发**最后一次**自动返工 | 1 → 2 |
| 第 3 次 REJECT | 仍未通过 | 停止自动返工；responsible_agent：`COMPLETED → HUMAN_REVIEW_REQUIRED`；全部依赖该 Artifact 的下游保持/变为 `BLOCKED` | 保持 2 |

**禁止无限返工循环**，尤其是 Critic ⇄ Demand Insight Agent 之间的循环——第 3 次 REJECT 必须停止自动返工并转人工介入，Supervisor 无权自行决定"再给一次机会"。

### 5.4 Knowledge Agent 的强制记录字段

每一次 REJECT（无论第几次）触发的返工，Supervisor 必须确保 Knowledge Agent 记录以下字段（缺一不可，见 [`agents/knowledge.md`](../agents/knowledge.md)）：

- `reject_reason`
- `retry_count`
- `responsible_agent`
- `previous_artifact`（被拒版本的 Artifact 引用）
- `revised_artifact`（返工后新版本的 Artifact 引用；发起返工时为待补，返工完成后补全）
- `previous_conclusion`（被拒版本中具体的结论/取值）
- `revised_conclusion`（返工后对应结论/取值的变化；同上，返工完成后补全）

### 5.5 Supervisor 的执行边界

Supervisor 只负责按上表执行状态迁移，不判断返工内容是否合理（这是 Gate/Critic 的职责），也不得在第 3 次 REJECT 后自行决定继续自动返工或跳过人工介入。

## 6. Gate 结果的执行（不含判定权）

- Gate 是独立、确定性、可审计的规则模块，**不是**第 13 个 Agent（见 [`gates/`](../gates/) 三份文件与 [`docs/AGENT_CONTRACT.md`](../docs/AGENT_CONTRACT.md) 中 Gate 与 Critic 的职责边界说明）。
- Gate 直接读取真实 Artifact（而不只是读取上游 Agent 的自述/摘要）做出判定，判定结果为 `PASS` / `CONDITIONAL` / `REJECT` / `HUMAN_REVIEW_REQUIRED` 之一。
- Supervisor 的职责仅限于：
  1. 在正确时机触发 Gate 执行（读取指定的真实 Artifact 集合）；
  2. 原样执行 Gate 的判定结果（`PASS`/按规则允许的 `CONDITIONAL` → 解锁对应下游；`REJECT` → 走第 5 节返工流程；`HUMAN_REVIEW_REQUIRED` → 走第 4 节）；
  3. 将判定结果与其依据（命中的规则 ID 或"未命中任何预定义规则"）转交 Knowledge Agent 记录。
- **Supervisor 没有权力自行修改 Gate 结论**——不得将 REJECT 改判为 CONDITIONAL 或 PASS，不得将 CONDITIONAL 改判为 PASS，也不得在 Gate 判定为 `HUMAN_REVIEW_REQUIRED` 时自行代为决定放行或拒绝。

## 7. CONDITIONAL 的执行规则

- 每道 Gate 必须在自己的 Gate 文件中预先写死：允许 CONDITIONAL 的情形、允许放行到的具体下游、必须携带的风险标记、以及绝不能 CONDITIONAL 的情形（见各 [`gates/`](../gates/) 文件的 Decision Rule Table）。
- Supervisor 可以且只能依据这些**已经写死的规则**自动执行 CONDITIONAL 放行——即：命中某条预定义规则 → 按该规则放行到指定下游，并把规则要求的风险标记一并透传给下游 Artifact 消费链路。
- 若当前情况的判定依据不被任何一条预定义规则覆盖（既不满足任何 PASS 规则，也不满足任何 CONDITIONAL 规则，甚至不清晰落在 REJECT 规则里），Gate 输出 `HUMAN_REVIEW_REQUIRED`，Supervisor 按第 4 节处理，不得凭主观判断代为归类到 PASS/CONDITIONAL/REJECT 中的任何一种。

## 8. 最终放行（Final Release）

- "最终放行"指 Action Agent 状态变为 `COMPLETED`，且 `action_plan.md` 通过 Evidence First 校验。
- Supervisor 在最终放行前必须核实：
  1. 三道 Gate 均已给出 `PASS` 或按规则允许的 `CONDITIONAL`（无一被绕过，也没有遗留在 `HUMAN_REVIEW_REQUIRED`）；
  2. 当前 `run_id` 下全部 13 个 Agent 的终态为 `COMPLETED`（Knowledge Agent 持续运行不要求"终止"，但其 `run_log.md` 必须已反映其余 12 个 Agent 的终态）；
  3. 无遗留 `FAILED` 或 `HUMAN_REVIEW_REQUIRED` 且未被处理的 Agent。
- 最终放行动作本身也是一条需要被 Knowledge Agent 记录的事件，须带上 `run_id`。

## 9. Supervisor 的自我约束

Supervisor 不得：
- 修改任何 Artifact 内容；
- 在 Gate 未 `PASS`/未按规则 `CONDITIONAL` 放行时以任何理由放行下游；
- 用自己的判断替代 Critic 的 REJECT/PASS 决定，或替代 Gate 的判定结论；
- 在第 3 次 REJECT 后自行决定继续自动返工，跳过 `HUMAN_REVIEW_REQUIRED`；
- 自行将 `HUMAN_REVIEW_REQUIRED` 迁移回 `READY`（该迁移只能由人工触发）；
- 替 Knowledge Agent 生成或修改 `run_log.md`；
- 替专业 Agent 生成业务 Artifact 内容；
- 跨 `run_id` 读取或混用 Artifact/状态（除非未来另有明确定义的跨运行知识调用机制）。
