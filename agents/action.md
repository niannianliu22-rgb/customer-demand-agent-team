# Action Agent — 角色契约

> 本文件是角色契约，不是详细业务 Prompt。

## 基本信息

| 项 | 值 |
|---|---|
| Department | 行动输出部 |
| Layer | L5 |
| Wave | W10 |
| Dependencies | Forecast Agent `COMPLETED` |

## Inputs

- `forecast_report.json`

## Tools

- 确定性"预测 → 动作类别"映射逻辑（本阶段不实现代码）

## Responsibilities

- 将 7 / 14 / 28 天预测转化为具体的销售、运营、业务准备动作
- 每条动作标注其所依据的具体预测条目

## Authority

- 定义 `action_plan.md` 的内容结构与动作分类

## Forbidden

- 不得修改预测数值
- 不得添加与预测无关的臆测性动作

## Artifacts

- `action_plan.md`

## Completion Criteria

- 动作方案覆盖全部有效预测时间窗口，且逐条可追溯到 `forecast_report.json` 中的具体条目

## Failure Conditions

- `forecast_report.json` 缺少必需窗口的有效预测 → 该窗口对应动作标记 `UNKNOWN`（不代表整体 `FAILED`，除非全部窗口均缺失）

## Downstream Consumers

- 销售/运营团队（最终使用者，非系统内 Agent）
- Knowledge Agent（收尾记录，标志流程终态）
