# FAILURE_PROPAGATION — 失败传播规则

## 1. 原则陈述

> **上游 FAILED 时，依赖它的下游必须 BLOCKED。**

失败不是局部事件，而是会沿依赖图向下传播的状态约束。系统绝不允许"上游失败了，但下游因为某种原因还是跑了"这种情况——这会导致下游基于不存在或不可信的证据产出结论，直接违反 Evidence First 原则。

## 2. `FAILED` 的判定边界

`FAILED` 特指 Agent 遇到**结构性障碍**、无法产出任何可用 Artifact 的情况，例如：

- 原始文件完全无法读取（Schema Mapping Agent）；
- 标准化后数据集完全无法生成（Data Standardization Agent）；
- 目标月份三年同期数据全部缺失（Historical Demand Pattern Agent，注意：*部分*缺失应走 `UNKNOWN`/`INSUFFICIENT_EVIDENCE` 标记后仍可 `COMPLETED`，只有*全部*缺失才判 `FAILED`）。

`FAILED` 与"产出了 Artifact，但其中部分条目标记 `UNKNOWN`/`INSUFFICIENT_EVIDENCE`"是两种不同的情况——后者是**部分完成**，Agent 状态仍为 `COMPLETED`，只是携带了需要下游谨慎处理的不确定性标记（见 [`policies/EVIDENCE_FIRST.md`](EVIDENCE_FIRST.md) 第 4 节）。判断某种情况该归为 `FAILED` 还是"`COMPLETED` 但含 `UNKNOWN`"，由各 Agent 自身在 [`docs/AGENT_MAP.md`](../docs/AGENT_MAP.md) 中定义的 Failure Conditions 决定。

## 3. 传播规则

1. 任一 Agent 状态变为 `FAILED`，Supervisor 立即将其**直接下游**（在依赖图中以它为依赖项的 Agent）状态设为/保持 `BLOCKED`；
2. 递归传播：直接下游被 `BLOCKED` 后，这些下游的下游同样必须保持 `BLOCKED`，直至传播到依赖图的末端；
3. 传播过程中，Gate 也被视为传播链路上的一环——若某 Gate 的输入 Agent `FAILED`，该 Gate 本身无法判定（既不能 PASS 也不能视为"跳过"），其后的全部 Agent 保持 `BLOCKED`；
4. 传播不因"下游 Agent 看起来不直接需要那个具体字段"而豁免——只要依赖图上存在路径，就必须传播，不做业务层面的选择性豁免（业务层面的选择性判断属于 Critic/专业 Agent 的职责，不属于失败传播机制）。

## 4. 传播的记录要求

每一次 `FAILED` 事件及其传播范围（被波及的全部下游 Agent 列表），必须被 Knowledge Agent 完整记录，形成可审计的影响面快照，供人工介入时快速定位问题源头与波及范围。

## 5. 恢复路径

`FAILED` 状态不会自动恢复。恢复需要：

1. 人工介入，确认导致 `FAILED` 的根本原因已解决（如原始文件已修复、数据源已补齐）；
2. 将该 Agent 状态由 `FAILED` 显式变更为 `BLOCKED`（不允许直接跳到 `READY`，必须重新走一次依赖判定，见 [`orchestration/STATE_MACHINE.md`](../orchestration/STATE_MACHINE.md)）；
3. 触发一次全量重扫（见 [`orchestration/RESCAN_RULES.md`](../orchestration/RESCAN_RULES.md)），让此前被传播 `BLOCKED` 的下游重新评估是否可转 `READY`。

## 6. 与 Critic REJECT 的区别

`FAILED` 传播 ≠ Critic REJECT 触发的返工循环：

- `FAILED` 传播：上游彻底无法产出，下游被阻断，需要人工介入修复根因；
- Critic REJECT：上游产出了 Artifact，但内容未通过审核，走的是 [`orchestration/ORCHESTRATOR_RULES.md`](../orchestration/ORCHESTRATOR_RULES.md) 第 5 节定义的返工流程（`COMPLETED → READY`），不进入本文件定义的失败传播路径。

两者不可混淆，Supervisor 必须准确区分当前面对的是哪一种情况。
