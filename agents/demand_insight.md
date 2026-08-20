# Demand Insight Agent — 角色契约

> 本文件是角色契约，不是详细业务 Prompt。

## 基本信息

| 项 | 值 |
|---|---|
| Department | 验证与洞察部 |
| Layer | L3 |
| Wave | W7（Critic REJECT 后重新进入本 Wave 返工） |
| Dependencies | Current Context Validation Agent `COMPLETED` |

## Inputs

- `validation_report.json`
- `historical_pattern_report.json`
- `academic_context_report.json`
- （返工时额外输入）上一轮 `critic_report.json` 中的 `rework_instruction`

## Tools

- 确定性综合逻辑（本阶段不实现代码）

## Responsibilities

- 综合历史规律、官方学业节点、适用性判定，形成具体的需求洞察条目
- 每条洞察必须可追溯到历史证据、官方来源与适用性判定（`evidence_refs`）

## Authority

- 起草洞察内容；在 Critic PASS 之前不具备最终效力

## Forbidden

- 不得给出 7/14/28 天的具体预测数字（属 Forecast Agent 职责）
- 不得自我认定通过（必须提交 Critic 审核）
- 不得输出无证据支撑的结论

## Artifacts

- `insight_report.json`（每轮返工版本号递增，如 v1、v2……）

## Completion Criteria

- 每条洞察均在 `evidence_refs` 中关联到具体证据 Artifact 条目 ID

## Failure Conditions

- 证据不足以支撑任何洞察条目 → 对应条目标记 `UNKNOWN` / `INSUFFICIENT_EVIDENCE`（不代表整体 `FAILED`，除非全部条目均无法支撑）

## Downstream Consumers

- Critic Agent
- Knowledge Agent
