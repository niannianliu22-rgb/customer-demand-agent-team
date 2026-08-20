# SOURCE_POLICY — 来源与结论追溯政策

> **核心一句话：无来源，不下结论。**

## 1. 原则陈述

任何进入 `insight_report.json`、`validation_report.json`、`forecast_report.json`、`action_plan.md` 的业务结论，必须能追溯到以下三类来源中的至少一类（通常需要多类叠加）：

1. **历史数据证据**：来自 `data/raw/` 原始表、经 `standardization_rules.json` 处理后落入 `unified_dataset.xlsx` 的具体记录范围，并经 `quality_report.json` 认证为可信；
2. **当前官方来源**：学校官方网站发布的学业节点信息，附完整 URL 与获取时间（记录于 `academic_context_report.json`）；
3. **对应 Artifact**：上游 Agent 产出的结构化 Artifact 中带 ID 的具体条目（如 `historical_pattern_report.json` 中某条统计结果的 ID）。

## 2. 官方来源的判定标准

"官方来源"specifically 指学校官方网站（含官方公告、官方招生/教务页面等由学校直接发布和维护的渠道）。以下**不构成**官方来源，不得作为学业节点判断的主要依据：

- 第三方教育资讯网站、论坛、社交媒体转发；
- 往年官方信息的缓存/截图（除非能确认与今年官方发布一致）；
- 内部猜测或"往年惯例应该也是这样"的推断——这类推断只能出现在 `unresolved` 标记中，并说明为何缺乏今年的官方确认。

Academic Context Agent 在无法找到官方来源时，必须将对应节点标记为 `UNKNOWN`/`INSUFFICIENT_EVIDENCE`，不得用非官方来源替代。

## 3. 历史数据作为来源的范围限定

按项目目标要求（见项目需求第 5、6 条），预测目标月份的历史规律分析**只使用目标月份在过去三年的同期数据**（如预测 2026 年 8 月，使用 2023/2024/2025 年 8 月数据）。

预测时点之前的最新业务走势（如 2026 年 7 月的走势）：

- **只能**作为可选校正信号，在 Current Context Validation Agent 阶段被显式引用；
- **不得**作为跨月份预测的主要依据；
- 若被引用，必须在对应 Artifact 中明确标注其角色为"辅助校正信号"，并说明为何不构成主要依据的替代。

## 4. 结论到来源的可追溯性要求

每条结论必须能沿以下链路回溯，且链路中每一环都必须是真实可读的 Artifact（而非口头描述）：

```
action_plan.md 中的动作
  ← forecast_report.json 中的预测条目
    ← insight_report.json 中通过 Critic PASS 的洞察条目
      ← validation_report.json 中的适用性判定
        ← historical_pattern_report.json 中的历史同期统计
        ← academic_context_report.json 中的官方学业节点
          ← data/raw/* 原始数据行 / 学校官方网站 URL
```

任何一环缺失来源引用，该结论视为不合格，必须在对应环节被 Critic REJECT 或被 Gate 拦截，不得放行。

## 5. 与 Evidence First 的关系

本政策是 [`EVIDENCE_FIRST.md`](EVIDENCE_FIRST.md) 在"来源"维度的具体化：Evidence First 关注"用什么证明完成/正确"，Source Policy 关注"业务结论的证据必须来自哪里、不能来自哪里"。两者共同构成 Critic Agent 审核时的核心检查依据。
