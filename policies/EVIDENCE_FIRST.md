# EVIDENCE_FIRST — 证据优先原则

> **核心一句话：Agent 自述只算 metadata；Artifact 才算真实证据。**

## 1. 原则陈述

任何 Agent 输出"我完成了""我认为该结论成立""数据已经清洗干净"这类自然语言陈述，在系统中只被视为**元数据（metadata）**——即"这个 Agent 报告了这件事"，而不是"这件事已被证实"。

只有以下内容才构成**证据（evidence）**：

- 真实存在、可读取的 Artifact 文件（如 `schema_mapping.json`、`unified_dataset.xlsx`）；
- Artifact 内部可核验的结构（是否符合 [`docs/AGENT_CONTRACT.md`](../docs/AGENT_CONTRACT.md) 定义的信封与字段）；
- Artifact 内部可核验的数字（如统计结果、行数、日期范围，且这些数字必须来自确定性工具计算，而非 Agent 直接生成）；
- Artifact 内部可核验的来源（如官方 URL、原始数据行范围引用）。

## 2. "我完成了"不能作为完成依据

Agent 状态变为 `COMPLETED` 是该 Agent 的自我声明，但**不是**下游/Gate/Critic/Supervisor 采信的依据本身。真正的判定必须回到：

1. 对应的 Artifact 文件是否真实存在；
2. 文件结构是否符合契约；
3. 文件内容中的关键字段（如 `items`、`evidence_refs`、`unresolved`）是否被正确填写，而非空壳或占位符。

任何环节（尤其是 Gate 判定与 Critic 审核）若发现"状态标记为 COMPLETED，但 Artifact 缺失/为空/结构不符",必须视为**未完成**，而不是信任状态标记。

## 3. 无计算，不判断

一切统计、合并、去重、日期转换、量化比较，必须由确定性工具（如 Python/pandas 之类的程序化计算）执行并把结果写入 Artifact，而不是由 Agent 在自然语言层面"估算"或"印象式判断"给出。Agent 的职责是**调用工具、解释工具输出、组织成结构化结论**，而不是自己心算出一个数字。

本阶段不实现具体计算代码，但该原则从架构阶段起就必须被写入每个数据类/统计类 Agent 的职责边界（见对应 `agents/*.md`）。

## 4. 无法验证时必须显式标记

当证据不足以支撑某个结论时，正确的做法**不是**：

- 省略该结论；
- 用模糊表述蒙混过关（如"大致""可能""通常"）；
- 强行给出一个数字或判断。

而是显式写入 Artifact 的 `unresolved` 字段，标记为：

- `UNKNOWN`：含义或方向不明确；
- `INSUFFICIENT_EVIDENCE`：有部分线索但不足以下结论。

这是一等公民字段，下游、Critic、Gate 都必须读取并纳入判断，而不是忽略。

## 5. 谁来执行这条原则

- **Gate**（Schema Gate / Data Gate / Insight Gate）：判定 PASS/REJECT 时只读 Artifact 结构化内容，不采信 Agent 的自然语言完成声明。
- **Critic Agent**：审核 `insight_report.json` 时，逐条核实 `evidence_refs` 是否真实指向上游 Artifact 中存在的内容，而不是相信洞察陈述本身听起来是否合理。
- **Knowledge Agent**：记录时只记录可核验的事实（状态变化、Artifact 版本、耗时等 metadata），不对业务结论的正确性做二次判断——但它记录的"完成"必须基于状态机的合法迁移，而这些迁移本身应已经过 Evidence First 校验。
- **Supervisor**：重扫依赖时，核实的是"上游 Artifact 可读"，不是"上游 Agent 说它完成了"。

## 6. 与其他文件的关系

- 来源相关的具体要求见 [`SOURCE_POLICY.md`](SOURCE_POLICY.md)；
- 失败/REJECT 情况下的传播规则见 [`FAILURE_PROPAGATION.md`](FAILURE_PROPAGATION.md)；
- Artifact 结构契约见 [`docs/AGENT_CONTRACT.md`](../docs/AGENT_CONTRACT.md)。
