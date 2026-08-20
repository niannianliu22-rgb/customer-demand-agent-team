# WAVE_PLAN — 第一版 Wave 设计

> **重要声明**：Wave 只定义"最早可以运行的时点"，**不是运行许可**。真正的运行许可只来自状态机中的 `READY`（见 [`STATE_MACHINE.md`](STATE_MACHINE.md)）。本文件是第一版设计，用于规划节奏与预期并行度，不得被实现为"Wave 到了就自动放行"的硬编码逻辑。
>
> **Run 范围声明**：Wave 进度按 `run_id` 独立计算（见 [`docs/AGENT_CONTRACT.md`](../docs/AGENT_CONTRACT.md) Run 隔离章节）。第一版只支持单 `run_id` 顺序执行一个预测目标月份，但 Wave 设计本身不得假设"全局只有一份 Wave 进度"。
>
> **本版本变更**：数据治理部新增 Data Intake Agent，插入在 Schema Mapping Agent 之前，全部下游 Wave 编号相应顺延一位（原 W1–W9 → 现 W2–W10）。

## 1. Wave 总览

| Wave | Agent | 说明 |
|---|---|---|
| W0 | Supervisor Agent（启动）、Knowledge Agent（开始记录） | 初始化，非业务 Agent；确定本次运行的 `run_id`，创建 `runs/{run_id}/` 目录结构 |
| W1 | **Data Intake Agent**、Academic Context Agent | 两者互不依赖，理论上可并行；Data Intake Agent 登记并扫描本次 run 的原始输入文件；Academic Context Agent 只需预测目标年月参数，不依赖内部数据管线 |
| W2 | Schema Mapping Agent | 依赖 Data Intake Agent `COMPLETED`；消费 `source_manifest.json` 与 `source_profiles/*.json`，不直接读取原始 Excel 文件 |
| — | **Schema Gate** | 直接检查 `source_manifest.json`、`source_profiles/*.json`、`schema_mapping.json`，判定四选一：`PASS`/`CONDITIONAL`/`REJECT`/`HUMAN_REVIEW_REQUIRED` |
| W3 | Data Standardization Agent | 依赖 Schema Gate `PASS`/按规则 `CONDITIONAL` |
| W4 | Data Quality Agent | 依赖 Data Standardization Agent `COMPLETED` |
| — | **Data Gate** | 检查 Data Quality Agent 产出（并直接核查 `unified_dataset`/`cleaning_log`/溯源信息），判定四选一 |
| W5 | Historical Demand Pattern Agent | 依赖 Data Gate `PASS`/按规则 `CONDITIONAL` |
| W6 | Current Context Validation Agent | 依赖 Historical Demand Pattern Agent `COMPLETED` **且** Academic Context Agent `COMPLETED`（两条链路在此汇合） |
| W7 | Demand Insight Agent | 依赖 Current Context Validation Agent `COMPLETED`；REJECT 返工重新进入本 Wave（受 2 次自动返工上限约束） |
| W8 | Critic Agent | 依赖 Demand Insight Agent `COMPLETED`；REJECT 触发 W7 返工循环（不产生新 Wave 编号），第 3 次未通过转 `HUMAN_REVIEW_REQUIRED` |
| — | **Insight Gate** | 检查 Critic Agent 判定结果（并直接抽样核查证据链），判定四选一 |
| W9 | Forecast Agent | 依赖 Insight Gate `PASS`/按规则 `CONDITIONAL` |
| W10 | Action Agent | 依赖 Forecast Agent `COMPLETED` |

Knowledge Agent 横跨 W0–W10 持续运行，不单独占用 Wave 编号；其 `run_log.md`（`runs/{run_id}/logs/run_log.md`）在 W10（Action Agent COMPLETED）后定稿。

**Gate 不是 Agent，不占用 Wave 编号内的 Agent 名额**——三道 Gate 均出现在两个 Wave 之间（"—"行），作为硬分隔。

## 2. 为什么这样分 Wave

- **W1 并行**：Data Intake Agent 与 Academic Context Agent 分属不同信息源（本次运行的原始输入文件 vs. 外部官方来源），互不依赖，最早可以同时开始。
- **Data Intake 先于 Schema Mapping**：Schema Mapping Agent 不再自己面对原始文件，而是消费 Data Intake Agent 已经登记、扫描过的结构化 Profile，这是"这是什么数据"与"这些字段代表什么业务含义"的职责分离（见 [`agents/data_intake.md`](../agents/data_intake.md)）。
- **Gate 作为 Wave 间的硬分隔**：Schema Gate、Data Gate、Insight Gate 都设置在两个 Wave 之间，强调"进入下一 Wave 不是因为上一 Wave 的 Agent 都跑完了，而是因为对应 Gate 判定通过"。
- **W6 是唯一的强制汇合点**：Current Context Validation Agent 必须等两条独立链路（历史规律链路 W1→W2→…→W5；官方情报链路 W1 的 Academic Context Agent）都 `COMPLETED`。
- **W7/W8 是循环区，不是单向 Wave**：Critic REJECT 会把 Demand Insight Agent 打回 `READY`，产生新一轮 W7→W8，受返工上限约束（同一 `issue_id` 最多 2 次自动返工）。

## 3. 本版 Wave 设计的已知局限（留待确认/迭代）

- 多 `run_id` 并行执行的调度策略仍未定义——第一版只支持单 `run_id` 顺序执行，架构已预留 `run_id` 隔离机制，但并行调度本身留待后续版本设计。
- 跨 `run_id` 的知识复用机制明确不在本版本范围内。
- Data Intake Agent 的"预期数据源清单"来源（即谁在 run 初始化时提供"本次应有 6 份数据源"这一信息）不在本阶段架构中详细定义，留待实现阶段明确（属于 W0 初始化职责的一部分，但具体机制未展开）。

## 4. 与状态机的关系重申

Wave 表中的顺序仅表示"设计预期"，实际执行时，每个 Agent 能否进入 `RUNNING`，完全由其在 [`STATE_MACHINE.md`](STATE_MACHINE.md) 中定义的 `BLOCKED → READY` 判定条件决定，且限定在当前 `run_id` 范围内。Supervisor 在每个 Wave 结束后必须执行全量重扫（见 [`RESCAN_RULES.md`](RESCAN_RULES.md)），而不是简单地"进入下一个 Wave 编号"。
