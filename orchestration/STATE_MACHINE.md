# STATE_MACHINE — 六状态与合法迁移

> 状态范围：本状态机描述的是**单个 run_id 内、单个 Agent 实例**的状态（见 [`docs/AGENT_CONTRACT.md`](../docs/AGENT_CONTRACT.md) 的 Run 隔离章节）。不同 run_id 之间的状态互不影响、互不可见。

## 1. 六状态定义

| 状态 | 含义 |
|---|---|
| `BLOCKED` | 至少一个依赖未 `COMPLETED`，或依赖已 `COMPLETED` 但其 Artifact 尚不可读/不满足契约结构；或所属链路的前置 Gate 未 PASS/未按规则 CONDITIONAL 放行；或上游处于 `FAILED`/`HUMAN_REVIEW_REQUIRED` |
| `READY` | 全部依赖 `COMPLETED` 且上游 Artifact 可读，且（若适用）前置 Gate 已 PASS 或按预定义规则 CONDITIONAL 放行——具备运行资格，等待 Supervisor 派发 |
| `RUNNING` | 已被 Supervisor 派发，Agent 正在执行任务 |
| `COMPLETED` | Agent 已产出符合契约结构的 Artifact，且自身声明任务完成（这只是自我终态，是否被下游/Gate/Critic 采信是另一回事） |
| `FAILED` | Agent 判定自身遇到结构性障碍，完全无法产出可用 Artifact |
| `HUMAN_REVIEW_REQUIRED` | 同一问题（`issue_id`，见 [`orchestration/ORCHESTRATOR_RULES.md`](ORCHESTRATOR_RULES.md) 第 5 节）已达到自动返工上限（累计 3 次判定未通过：初始 1 次 + 自动返工 2 次），系统停止自动返工，等待人工介入；或 Gate 在 CONDITIONAL 判定时遇到预定义规则未覆盖的情况 |

`HUMAN_REVIEW_REQUIRED` 是本版本新增状态，专用于表达"系统不能、也不允许自己继续做决定"的情形——它既可能落在某个 Agent 实例上（返工次数耗尽），也可能是某次 Gate 判定的输出结果（见 [`gates/`](../gates/) 三份文件），二者的处理方式在第 4 节区分说明。

## 2. 合法状态迁移

```
BLOCKED  --(全部依赖COMPLETED 且 Artifact可读 且 前置Gate PASS/CONDITIONAL放行)-->  READY
READY    --(Supervisor派发)-->  RUNNING
RUNNING  --(产出符合契约的Artifact)-->  COMPLETED
RUNNING  --(结构性障碍，无法产出)-->  FAILED

COMPLETED --(同一issue_id，第1次REJECT)-->  READY            [retry_count: 0→1]
COMPLETED --(同一issue_id，第2次REJECT)-->  READY            [retry_count: 1→2，标记"最后一次自动返工"]
COMPLETED --(同一issue_id，第3次REJECT，retry_count已为2)-->  HUMAN_REVIEW_REQUIRED   [停止自动返工]

FAILED               --(人工介入，确认根因已修复)-->  BLOCKED   [重新走一次依赖判定]
HUMAN_REVIEW_REQUIRED --(人工审阅并明确授权重试)-->  READY     [retry_count 重置为 0]
```

不存在的迁移（显式禁止）：

- `BLOCKED → RUNNING`（必须先经过 `READY`）；
- `FAILED → COMPLETED` / `HUMAN_REVIEW_REQUIRED → COMPLETED`（不允许绕过重新执行直接判定成功）；
- `COMPLETED → BLOCKED`（REJECT 的去向是 `READY`（返工次数未耗尽）或 `HUMAN_REVIEW_REQUIRED`（返工次数已耗尽），不是 `BLOCKED`——因为其依赖仍然满足，只是产出未达标）；
- `HUMAN_REVIEW_REQUIRED → READY` 只能由**人工动作**触发，Supervisor 不得自动执行此迁移（自动执行会架空"人工介入"的设计意图）。

## 3. Reject 计数与迁移的对应关系

完整规则见 [`orchestration/ORCHESTRATOR_RULES.md`](ORCHESTRATOR_RULES.md) 第 5 节。核心表：

| 判定序号（同一 `issue_id`） | 结果 | 状态迁移 | retry_count |
|---|---|---|---|
| 第 1 次 REJECT | 未通过 | `COMPLETED → READY`，自动返工 | 0 → 1 |
| 第 2 次 REJECT | 未通过 | `COMPLETED → READY`，标记"最后一次自动返工" | 1 → 2 |
| 第 3 次 REJECT | 仍未通过 | `COMPLETED → HUMAN_REVIEW_REQUIRED`，停止自动返工 | 保持 2（返工已用尽，不再递增） |

`issue_id` 是同一问题的稳定标识（例如 Critic 对 `insight_report.json` 中某条洞察 `items[i].id` 的持续质疑，或 Gate 对同一检查项的持续判定），不同 `issue_id` 的 REJECT 各自独立计数，不得合并计数（避免不相关的新问题被误判为"已达上限"）。

此规则统一适用于：Schema Gate REJECT → Schema Mapping Agent；Data Gate REJECT → Data Standardization Agent（或视问题定位回退至 Schema Mapping Agent）；Critic REJECT → Demand Insight Agent。**禁止任何一条链路出现无上限的自动返工循环**，尤其是 Critic ⇄ Demand Insight 循环。

## 4. `HUMAN_REVIEW_REQUIRED` 的两种触发路径

1. **Agent 侧**：某 Agent 产出的 Artifact 针对同一 `issue_id` 累计第 3 次被 REJECT（已用尽 2 次自动返工）→ 该 Agent 状态置为 `HUMAN_REVIEW_REQUIRED`。
2. **Gate 侧**：Gate 在执行 CONDITIONAL 判定时，遇到当前情况不被其预定义规则表覆盖（见各 [`gates/`](../gates/) 文件中的 Decision Rule Table）→ Gate 本次判定结果直接输出为 `HUMAN_REVIEW_REQUIRED`（而非 Supervisor 主观决定），对应的上游 Agent 状态维持 `COMPLETED`（它已合规产出 Artifact，问题出在 Gate 规则未能覆盖判定，而非 Agent 产出有误），但下游进入 `BLOCKED`（见第 5 节）。

两种情形都不允许 Supervisor 用主观判断替代——Supervisor 只能执行既定规则得出的结果，不能"拍板"REJECT 改 CONDITIONAL、CONDITIONAL 改 PASS，或反之。

## 5. 下游联动规则

- 上游 `FAILED` ⇒ 全部直接与间接依赖它的下游，必须处于/保持 `BLOCKED`（见 [`policies/FAILURE_PROPAGATION.md`](../policies/FAILURE_PROPAGATION.md)）。
- 上游（Agent 或 Gate 判定）进入 `HUMAN_REVIEW_REQUIRED` ⇒ 全部直接与间接依赖它的下游，同样必须处于/保持 `BLOCKED`，直至人工介入将其迁移回 `READY`（Agent 侧）或人工修订 Gate 规则并重新判定（Gate 侧）。
- 上游从 `COMPLETED` 被打回 `READY`（返工中，未达上限）⇒ 下游若已基于旧版本 Artifact 进入 `READY`/`RUNNING`/`COMPLETED`，必须被重新置为 `BLOCKED`，等待上游新版本 `COMPLETED` 后重新判定。

## 6. Gate 判定结果与状态机的关系

Gate 判定结果现有四种：`PASS` / `CONDITIONAL` / `REJECT` / `HUMAN_REVIEW_REQUIRED`。Gate 不是 Agent，不拥有本文件定义的六状态实例，但其判定结果直接决定下游 Agent 能否从 `BLOCKED` 转 `READY`（`PASS` 或按规则放行的 `CONDITIONAL`）、还是必须停留 `BLOCKED`（`REJECT` 触发上游返工循环、或 `HUMAN_REVIEW_REQUIRED` 触发人工介入）。详见 [`gates/`](../gates/) 三份文件与 [`docs/AGENT_CONTRACT.md`](../docs/AGENT_CONTRACT.md) 中 Gate 与 Critic 的职责边界说明。

## 7. Wave 与状态机的关系

Wave 号只标注"最早可能进入 READY 判定的时点"，不出现在状态迁移规则中，且 Wave 进度按 `run_id` 独立计算（见 [`WAVE_PLAN.md`](WAVE_PLAN.md)）。
