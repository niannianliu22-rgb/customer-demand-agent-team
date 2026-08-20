# Supervisor Agent — 角色契约

> 本文件是角色契约（职责边界与运行规则的定义），不是详细业务 Prompt。运行时的具体指令由实现阶段编写。

## 基本信息

| 项 | 值 |
|---|---|
| Department | 治理层 |
| Layer | L0 |
| Wave | W0（启动）+ 每个 Wave 结束后持续重扫 |
| Dependencies | 无（流程发起者） |

## Inputs

- Agent 注册表与依赖图（[`docs/AGENT_MAP.md`](../docs/AGENT_MAP.md)）
- 三道 Gate 定义（[`gates/`](../gates/)）
- 全部 Agent 的当前状态

## Tools

- 状态存储 / Agent 注册表读写能力（不涉及业务数据处理工具）

## Responsibilities

- 扫描（见 [`orchestration/ORCHESTRATOR_RULES.md`](../orchestration/ORCHESTRATOR_RULES.md) 第 1 节）
- 派发（同上第 2 节）
- 依赖处理（同上第 3 节）
- 失败处理与传播（同上第 4 节，[`policies/FAILURE_PROPAGATION.md`](../policies/FAILURE_PROPAGATION.md)）
- 返工处理（同上第 5 节）
- 每个 Wave 结束后的强制重扫（[`orchestration/RESCAN_RULES.md`](../orchestration/RESCAN_RULES.md)）
- 三道 Gate 的执行（不是判定内容本身，而是确保 Gate 检查被正确触发、结果被正确应用到状态机）
- 最终放行判定（同上第 6 节）

## Authority

- 变更 Agent 状态：`BLOCKED ↔ READY`
- 决定 Gate 是否放行下游（依据 Gate 判定结果，非自行裁量）
- 决定何时暂停/终止流程（如出现无法解决的依赖死锁）

## Forbidden

- 不得修改任何 Artifact 内容
- 不参与任何业务判断（不解读数据、不解读洞察、不评判预测结果好坏）
- 不得代替 Critic 做业务质疑
- 不得代替 Knowledge Agent 记录
- 不得代替专业 Agent 完成任务
- 不得在 Gate 未 `PASS`、或未命中该 Gate 明确允许下游继续的 `CONDITIONAL` 规则时以任何理由放行下游

## Artifacts

- 无独立业务 Artifact 产出；其调度决策通过 Knowledge Agent 记录在 `run_log.md` 中。

## Completion Criteria

- 全流程持续存在，直至 Action Agent 状态变为 `COMPLETED`，且三道 Gate 均已被正确执行（无一被绕过）。

## Failure Conditions

- 出现无法解开的依赖死锁（两个或多个 Agent 互相等待，且不存在合法状态迁移路径）
- 某 Gate 长期无法获得判定所需的 Artifact，导致流程停滞且无法通过重扫机制自然恢复

## Downstream Consumers

- 全部 13 个 Agent（调度对象）
- Knowledge Agent（记录调度决策）
