# RESCAN_RULES — Wave 结束后的自动重扫机制

> **Run 范围声明**：重扫在单个 `run_id` 内执行，覆盖该 `run_id` 下的全部 13 个 Agent。若未来存在多个并行 `run_id`，每个 `run_id` 独立触发、独立执行重扫，互不覆盖、互不影响（见 [`docs/AGENT_CONTRACT.md`](../docs/AGENT_CONTRACT.md) Run 隔离章节）。

## 1. 为什么需要重扫

Wave 只是一个规划工具（见 [`WAVE_PLAN.md`](WAVE_PLAN.md)），不是运行许可来源。真正决定一个 Agent 能否运行的是它的状态是否为 `READY`。如果没有强制重扫机制，可能出现：

- 某 Agent 的依赖在本 Wave 中途才被满足，但因为不在"预期的 Wave 顺序"里而被遗漏，一直停留在 `BLOCKED`；
- 某 Agent 因 REJECT 被打回 `READY` 后，没有被及时重新纳入派发考虑；
- Gate `PASS`/`CONDITIONAL` 后，理论上应转 `READY` 的下游 Agent 没有被及时发现；
- 某 Agent 因返工上限耗尽进入 `HUMAN_REVIEW_REQUIRED`，其下游未被及时确认仍处于 `BLOCKED`。

重扫机制就是为了系统性防止"遗漏"。

## 2. 触发时机

Supervisor 必须在以下时机执行一次全量重扫：

1. **每个 Wave 结束后**（即该 Wave 内所有已派发的 Agent 都到达 `COMPLETED`、`FAILED` 或 `HUMAN_REVIEW_REQUIRED` 终态）；
2. 任一 Gate 做出 `PASS`/`CONDITIONAL`/`REJECT`/`HUMAN_REVIEW_REQUIRED` 判定后；
3. Critic Agent 做出 `PASS`/`REJECT` 判定后；
4. 任一 Agent 状态变为 `FAILED` 或 `HUMAN_REVIEW_REQUIRED` 后（用于确认下游传播已正确覆盖）；
5. 人工介入将某 Agent 由 `HUMAN_REVIEW_REQUIRED` 迁移回 `READY`、或由 `FAILED` 迁移回 `BLOCKED` 后。

## 3. 重扫动作

对当前 `run_id` 下**全部**未处于 `RUNNING`/`COMPLETED`（终态且未被 REJECT）的 Agent，逐一执行：

1. 读取该 Agent 在 [`docs/AGENT_MAP.md`](../docs/AGENT_MAP.md) 中定义的 `Dependencies`；
2. 检查每个依赖 Agent 的当前状态是否为 `COMPLETED`；
3. 若全部依赖 `COMPLETED`，进一步核实对应 Artifact 是否可读、是否符合 [`docs/AGENT_CONTRACT.md`](../docs/AGENT_CONTRACT.md) 定义的信封结构（含正确的 `run_id`）；
4. 若该 Agent 的依赖链路上存在前置 Gate，额外核实该 Gate 判定是否为 `PASS`，或按其规则表判定为 `CONDITIONAL` 且允许该下游继续；
5. 若上述条件全部满足，且该 Agent 当前状态为 `BLOCKED`，则将其状态变更为 `READY`；
6. 若任一依赖处于 `FAILED` 或 `HUMAN_REVIEW_REQUIRED`，则确保该 Agent 状态为/保持 `BLOCKED`（不得误转 `READY`）。

## 4. 重扫的完整性要求

- 重扫必须覆盖当前 `run_id` 下**全部 13 个 Agent**，不得只检查"预期在当前 Wave 运行"的子集；
- 重扫是幂等操作：多次重扫同一状态快照，结果应一致，不产生副作用；
- 重扫本身不派发任务，只做状态判定；派发是重扫之后的独立动作（见 [`ORCHESTRATOR_RULES.md`](ORCHESTRATOR_RULES.md) 第 2 节）；
- 重扫不得跨 `run_id` 读取或影响其他运行的状态。

## 5. 重扫与返工循环的关系

Critic REJECT 或 Gate REJECT 触发的返工（未达返工上限时），会把某个 `COMPLETED` 的 Agent 打回 `READY`。此时必须触发一次重扫，因为：

- 依赖该 Agent 的下游此前可能已基于旧版本 Artifact 进入 `READY`/`RUNNING`/`COMPLETED`，需要被重新置为 `BLOCKED`（见 [`STATE_MACHINE.md`](STATE_MACHINE.md) 第 5 节）；
- 重扫负责发现这些"基于过期证据"的下游状态，并纠正它们。

若返工已达上限（第 3 次 REJECT），Agent 转为 `HUMAN_REVIEW_REQUIRED` 而非 `READY`，重扫此时的职责是确保全部下游被正确置为/保持 `BLOCKED`，而不是错误地寻找"是否有依赖已满足"（因为该 Agent 本身不再产出新版本，直至人工介入）。

## 6. 记录要求

每次重扫的输入快照（重扫前各 Agent 状态）与输出结果（发生的状态变更列表），连同 `run_id`，都必须提供给 Knowledge Agent 记录，形成可审计的重扫历史。

## 7. 本阶段留白

- 重扫的具体触发实现方式（事件驱动 vs. 轮询）不在本阶段架构范围内定义，留待实现阶段决定。
- 重扫失败/异常情况的处理（如状态存储不可读）不在本阶段定义，留待实现阶段补充。
- 多 `run_id` 并行时，重扫任务的调度与资源隔离方式留待后续版本设计（第一版仅保证单 `run_id` 重扫逻辑本身不假设全局单例）。
