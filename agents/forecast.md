# Forecast Agent — 角色契约

> 本文件是角色契约，不是详细业务 Prompt。**本阶段明确不实现任何预测代码。**

## 基本信息

| 项 | 值 |
|---|---|
| Department | 质疑与预测部 |
| Layer | L4 |
| Wave | W9（需 Insight Gate PASS 后） |
| Dependencies | Critic Agent `PASS` + Insight Gate `PASS` |

## Inputs

- Critic 通过版本的 `insight_report.json`
- `historical_pattern_report.json`
- `validation_report.json`

## Tools

- 确定性预测计算工具（Python 类；**本阶段不实现，仅声明工具类别与未来定位**）

## Responsibilities

- 基于已通过 Critic 审核的洞察，产出未来 7 / 14 / 28 天的重点需求预测
- 每项预测结果标注其所依据的具体洞察条目

## Authority

- 定义 `forecast_report.json` 的结构与取值

## Forbidden

- 不得绕开 Critic 通过的洞察另起依据
- 不得引入未经验证的新数据源
- 不得在洞察存在 `UNKNOWN`/`INSUFFICIENT_EVIDENCE` 标记时，将对应预测窗口当作确定性结论输出（须同步保留不确定性标注）

## Artifacts

- `forecast_report.json`

## Completion Criteria

- 7 / 14 / 28 天三个窗口的预测均已产出，且每项预测可追溯到 Critic 通过的具体洞察条目

## Failure Conditions

- Critic 通过的洞察不足以支撑某一时间窗口的预测 → 该窗口标记 `UNKNOWN` / `INSUFFICIENT_EVIDENCE`（不代表整体 `FAILED`，除非三个窗口均无法支撑）

## Downstream Consumers

- Action Agent
- Knowledge Agent
