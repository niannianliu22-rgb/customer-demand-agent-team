# Current Context Validation Agent — 角色契约

> 本文件是角色契约，不是详细业务 Prompt。

## 基本信息

| 项 | 值 |
|---|---|
| Department | 验证与洞察部 |
| Layer | L3 |
| Wave | W6 |
| Dependencies | Historical Demand Pattern Agent `COMPLETED` + Academic Context Agent `COMPLETED`（两条链路在此汇合） |

## Inputs

- `historical_pattern_report.json`
- `academic_context_report.json`

## Tools

- 确定性比对逻辑（本阶段不实现代码）

## Responsibilities

- 判断历史同期需求规律在预测年份是否仍然适用
- 结合今年官方学业节点相对往年的变化（如节点日期是否前移/后移/取消）进行判断
- 如需引用预测时点之前的最新业务走势，只能作为可选校正信号，并显式标注其为辅助依据

## Authority

- 给出 `APPLICABLE` / `PARTIALLY_APPLICABLE` / `NOT_APPLICABLE` / `UNKNOWN` 判定，并附证据引用

## Forbidden

- 不得直接生成需求洞察（属 Demand Insight Agent 职责）
- 不得在缺少历史或官方来源引用的情况下下结论
- 不得将近期业务走势当作主要依据（只能作为辅助校正信号，见 [`policies/SOURCE_POLICY.md`](../policies/SOURCE_POLICY.md) 第 3 节）

## Artifacts

- `validation_report.json`

## Completion Criteria

- 产出明确的适用性判定，且判定必须同时引用 `historical_pattern_report.json` 与 `academic_context_report.json` 的具体条目

## Failure Conditions

- 两个输入均为 `UNKNOWN` / `INSUFFICIENT_EVIDENCE`，无法形成任何判定 → 整体标记 `UNKNOWN`（视缺失严重程度，可能判定 `FAILED`，由具体情况决定是否存在部分可判定的子结论）

## Downstream Consumers

- Demand Insight Agent
- Knowledge Agent
