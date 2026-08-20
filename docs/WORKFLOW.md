# WORKFLOW — 完整工作流

> 本文件描述从原始输入文件到最终 `action_plan.md` 的完整流程，并标注每个环节允许的判定类型：`PASS` / `CONDITIONAL` / `REJECT` / `RETRY` / `BLOCKED` / `FAILED` / `HUMAN_REVIEW_REQUIRED`。全部流程限定在单一 `run_id` 范围内（见 [`docs/AGENT_CONTRACT.md`](AGENT_CONTRACT.md) 第 6 节）。

## 1. 流程图

```mermaid
flowchart TD
    RAW["runs/{run_id}/input/<br/>本次run的原始Excel文件 + 预测目标年月"]

    DI["Data Intake Agent<br/>W1<br/>（登记+调用inspect_excel.py扫描）"]
    AC["Academic Context Agent<br/>W1（与Data Intake并行）"]

    SM["Schema Mapping Agent<br/>W2<br/>（消费source_manifest+profiles）"]

    GATE1{{"Schema Gate<br/>直读source_manifest+source_profiles+schema_mapping<br/>PASS/CONDITIONAL/REJECT/HUMAN_REVIEW_REQUIRED"}}

    DS["Data Standardization Agent<br/>W3"]
    DQ["Data Quality Agent<br/>W4"]

    GATE2{{"Data Gate<br/>直读unified_dataset+cleaning_log+溯源<br/>PASS/CONDITIONAL/REJECT/HUMAN_REVIEW_REQUIRED"}}
    PUB["Deterministic Data Product Publisher<br/>PASS→data/processed stable<br/>CONDITIONAL→data/processed/candidate"]

    HDP["Historical Demand Pattern Agent<br/>W5"]
    CCV["Current Context Validation Agent<br/>W6"]
    DI2["Demand Insight Agent<br/>W7"]
    CR["Critic Agent（业务推理质疑）<br/>W8"]

    GATE3{{"Insight Gate<br/>直读critic_report+insight_report+证据链<br/>PASS/CONDITIONAL/REJECT/HUMAN_REVIEW_REQUIRED"}}

    FC["Forecast Agent<br/>W9"]
    AA["Action Agent<br/>W10"]

    HR[("HUMAN_REVIEW_REQUIRED<br/>同一issue_id第3次未通过<br/>下游全部BLOCKED")]

    KA[("Knowledge Agent<br/>全程记录 run_log.md<br/>（含source_id/issue_id/retry_count等字段）")]

    RAW --> DI
    RAW --> AC
    DI -- "source_manifest.json<br/>source_profiles/*.json" --> SM
    SM -- "schema_mapping.json" --> GATE1
    GATE1 -- "PASS / CONDITIONAL(按规则)" --> DS
    GATE1 -- "REJECT (第1/2次，回退Data Intake或Schema Mapping)" -.-> SM
    GATE1 -- "REJECT第3次 或 规则未覆盖" --> HR

    DS -- "standardization_rules.json<br/>unified_dataset.xlsx" --> DQ
    DQ -- "quality_report.json" --> GATE2
    GATE2 -- "PASS / CONDITIONAL(按规则，目标月份数据除外)" --> HDP
    GATE2 -- "PASS / CONDITIONAL" --> PUB
    GATE2 -- "REJECT (第1/2次)" -.-> DS
    GATE2 -- "REJECT第3次 或 规则未覆盖" --> HR

    HDP -- "historical_pattern_report.json" --> CCV
    AC -- "academic_context_report.json" --> CCV

    CCV -- "validation_report.json" --> DI2
    DI2 -- "insight_report.json" --> CR
    CR -- "critic_report.json: PASS" --> GATE3
    CR -- "critic_report.json: REJECT (第1/2次，RETRY)" -.-> DI2
    CR -- "REJECT第3次（同一issue_id）" --> HR

    GATE3 -- "PASS / CONDITIONAL(按规则)" --> FC
    GATE3 -- "结构性REJECT / 规则未覆盖" --> HR
    FC -- "forecast_report.json" --> AA
    AA -- "action_plan.md" --> DONE(["runs/{run_id}/final/<br/>交付：销售/运营/业务准备动作"])

    DI -.-> KA
    AC -.-> KA
    SM -.-> KA
    DS -.-> KA
    DQ -.-> KA
    HDP -.-> KA
    CCV -.-> KA
    DI2 -.-> KA
    CR -.-> KA
    FC -.-> KA
    AA -.-> KA
    HR -.-> KA
```

## 2. 判定类型定义表

| 判定 | 含义 | 发生在哪里 | 触发的后续动作 |
|---|---|---|---|
| `PASS` | Gate 判定完全达标；Critic 判定某洞察成立 | 三道 Gate；Critic Agent | 下游对应依赖满足，可能从 `BLOCKED` → `READY` |
| `CONDITIONAL` | Gate 判定达到"预定义规则允许放行，但带风险标记"的情形。**`CONDITIONAL` 不等于 `PASS`** | 三道 Gate（仅当命中其 Decision Rule Table 中的 CONDITIONAL 规则时） | 按规则放行到指定下游，风险标记随 Artifact 链路透传，下游必须在其产出中体现该风险标记 |
| `REJECT` | Gate 判定未达标；Critic 判定某洞察不成立 | 三道 Gate；Critic Agent | 若同一 `issue_id` 累计 REJECT 次数 ≤ 2：触发 `RETRY`；若达到第 3 次：转 `HUMAN_REVIEW_REQUIRED` |
| `RETRY` | 因 REJECT 触发的返工（同一 `issue_id` 第 1、2 次） | Schema Gate REJECT → Data Intake Agent（数据源问题）或 Schema Mapping Agent（映射问题）重跑；Data Gate REJECT → Data Standardization Agent 重跑；Critic REJECT → Demand Insight Agent 重跑 | 返工次数、原因由 Knowledge Agent 记录（7 项必录字段）；Artifact 版本号递增；重新提交原判定方 |
| `BLOCKED` | Agent 尚不满足运行条件 | 任意 Agent，依赖未满足、上游 `FAILED`/`HUMAN_REVIEW_REQUIRED`、或前置 Gate 未放行时 | 等待 Supervisor 重扫；条件满足后转 `READY` |
| `FAILED` | Agent 判定自身彻底无法产出任何可用 Artifact（结构性障碍） | 任意 Agent，符合其 Failure Conditions 时 | 依赖它的下游必须 `BLOCKED`（见 [`policies/FAILURE_PROPAGATION.md`](../policies/FAILURE_PROPAGATION.md)），需要人工介入 |
| `HUMAN_REVIEW_REQUIRED` | 同一 `issue_id` 累计 3 次判定未通过；或 Gate 遇到预定义规则未覆盖的情形 | 责任 Agent（返工耗尽）；Gate 本身（规则覆盖不到）| 停止自动决策；依赖它的下游必须 `BLOCKED`；等待人工介入后按 [`orchestration/STATE_MACHINE.md`](../orchestration/STATE_MACHINE.md) 定义的路径恢复 |

## 3. 关键分支说明

### 3.0 Data Intake 阶段（本版本新增，无 Gate，靠 Completion Criteria 自我把关）
- Data Intake Agent 与 Academic Context Agent 并行于 W1，互不依赖。
- Data Intake Agent 不设独立 Gate——它只要满足 [`agents/data_intake.md`](../agents/data_intake.md) 的 8 条完成标准（全部文件登记、无静默遗漏、数量可核对）即可 `COMPLETED`，即使部分数据源 `MISSING`/`UNREADABLE` 也不影响其自身完成。
- 数据源缺失是否可以继续，留给下一环节的 **Schema Gate** 判定（见 3.1），而不是由 Data Intake Agent 自己决定要不要往下走。

### 3.1 Schema Gate 分支
- **PASS / CONDITIONAL（按规则）**：Data Standardization Agent 从 `BLOCKED` → `READY`；`CONDITIONAL` 时风险标记随链路透传。
- **REJECT（第 1、2 次）**：按问题定位回退——若问题源于数据源本身（缺失/不可读落在需要的范围、或 manifest 与实际不符），回退给 **Data Intake Agent**；若问题源于字段映射本身，回退给 **Schema Mapping Agent**。触发 RETRY，版本号递增后重新提交 Schema Gate。
- **REJECT 第 3 次 / 规则未覆盖**：责任 Agent 转 `HUMAN_REVIEW_REQUIRED`，Data Standardization Agent 保持 `BLOCKED`，等待人工介入。

### 3.2 Data Gate 分支
- **PASS / CONDITIONAL（按规则，目标月份同期数据范围内问题永不 CONDITIONAL）**：Historical Demand Pattern Agent 从 `BLOCKED` → `READY`。两者的发布权限不同：`PASS` 才允许将最终验收的 `unified_dataset.xlsx` 发布为 `data/processed/` stable 产品；`CONDITIONAL` 仅允许发布到 `data/processed/candidate/` 并标记 `release_status=CONDITIONAL`。
- **REJECT（第 1、2 次）**：问题回退给 Data Standardization Agent 或进一步回退给 Schema Mapping Agent（由 Gate 判定的问题定位决定），触发 RETRY。
- **REJECT 第 3 次 / 规则未覆盖**：对应责任 Agent 转 `HUMAN_REVIEW_REQUIRED`，Historical Demand Pattern Agent 保持 `BLOCKED`；两种情形均禁止发布 processed 数据产品。

### 3.2.1 标准数据产品发布（Data Gate 后）
- 发布器不是 Agent，不参与状态机或业务判断；它只能读取已验收的运行 Artifact 并生成版本化副本。
- stable 的全部前置条件为：Data Intake `COMPLETED`、Schema Mapping `COMPLETED`、Schema Gate `PASS`、Data Standardization `COMPLETED`、Data Quality `COMPLETED`、Data Gate `PASS`。
- 发布后的产品由其他项目、推广中台、BI 与 Agent Team 直接从 `data/processed/` 读取；运行证据继续只保存在 `runs/{run_id}/artifacts/`。详细契约见 [`docs/DATA_PRODUCT_RELEASE.md`](DATA_PRODUCT_RELEASE.md)。

### 3.3 Critic ⇄ Demand Insight 循环（受返工上限约束）
- Critic REJECT 某条洞察（`issue_id` = 该洞察条目）→ `critic_report.json` 标注 `rework_instruction` → 若同一 `issue_id` 累计 REJECT ≤ 2 次：Demand Insight Agent 状态由 `COMPLETED` 变回 `READY`（RETRY）→ 产出新版本 `insight_report.json` → 重新提交 Critic 审核。
- 若同一 `issue_id` 累计 REJECT 达第 3 次：**循环强制停止**，Demand Insight Agent 转 `HUMAN_REVIEW_REQUIRED`，等待人工介入。**禁止无限循环**。

### 3.4 Insight Gate 分支
- **PASS / CONDITIONAL（按规则）**：Forecast Agent 从 `BLOCKED` → `READY`。Insight Gate 不重新评判洞察的业务对错，只核验 Critic 审核过程本身的完整性、证据链可验证性、来源政策合规性。
- **REJECT**：不进入 Forecast 阶段，流程停留在 Critic ⇄ Demand Insight 循环（受第 3.3 节返工上限约束）。
- **规则未覆盖**：Gate 输出 `HUMAN_REVIEW_REQUIRED`，Forecast Agent 保持 `BLOCKED`。

## 4. 并行与汇合点

- **并行起点**：Data Intake Agent 与 Academic Context Agent 同属 Wave 1，互不依赖，可并行运行。
- **串行分工**：Schema Mapping Agent（W2）必须等待 Data Intake Agent（W1）`COMPLETED` 后才能开始——它消费的是 Data Intake 已经登记、扫描好的结构化 Profile，不自己重新读取原始文件。
- **汇合点**：Current Context Validation Agent 需要同时等待 Historical Demand Pattern Agent 与 Academic Context Agent 都 `COMPLETED`，才能从 `BLOCKED` 转 `READY`。

## 5. Knowledge Agent 的横切记录

Knowledge Agent 不出现在主链路的判定中，但对图中每一个 Agent 的状态变化（含 `HUMAN_REVIEW_REQUIRED`）、每一次 Gate 判定（四态）、每一次 Critic 循环（含 7 项返工必录字段）都进行旁路记录，对 Data Intake Agent 额外记录 `inspect_excel.py` 调用情况与 `source_id` 分配，最终形成完整的 `run_log.md`（`runs/{run_id}/logs/`）。

## 6. Gate 与 Critic 的边界重申

Critic 负责业务推理层面的质疑（"这条结论对不对"），Insight Gate 独立、直接核查 `critic_report.json` 与 `insight_report.json` 的结构完整性、证据引用的真实性、来源政策合规性（"审核过程全不全、证据真不真"）。同理，Schema Gate 也不重新判断字段的业务语义对不对（那是 Schema Mapping Agent 的职责），只核查其映射结果是否与 Data Intake Agent 提供的真实结构 Profile 一致、是否有遗漏。详见 [`docs/AGENT_CONTRACT.md`](AGENT_CONTRACT.md) 第 5 节与 [`gates/`](../gates/) 各文件。

## 7. Data Intake 与 Schema Mapping 的边界重申

Data Intake Agent 回答"这是什么数据、结构是什么"（如"2023 学管.xlsx，字段：咨询时间、院校、任务、金额"，附 dtype、缺失率等结构特征）；Schema Mapping Agent 才回答"这些字段业务上代表什么"（如"咨询时间 → `consultation_date`"）。前者产出的 `source_profiles` 是确定性工具 `inspect_excel.py` 的扫描结果，后者产出的 `schema_mapping.json` 是业务语义判断的结果——两者不得合并为一个 Agent，避免"客观结构事实"与"主观业务解释"混在同一次产出中而难以分别核验。
