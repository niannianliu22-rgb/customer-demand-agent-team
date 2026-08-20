# AGENT_MAP — 13 个 Agent 档案

> 每个 Agent 的完整档案：Name / Department / Layer / Wave / Dependencies / Inputs / Tools / Responsibilities / Authority / Forbidden / Artifacts / Completion Criteria / Failure Conditions / Downstream Consumers。
>
> 详细角色契约见 [`agents/`](../agents/) 目录下对应文件；本文件是全局速查表。
>
> **通用说明（适用于全部 13 个 Agent，以下不逐条重复）**：
> - 全部 Agent 的 Inputs/Artifacts 均隐式携带 `run_id` 字段，遵循 [`docs/AGENT_CONTRACT.md`](AGENT_CONTRACT.md) 的信封定义；Agent 不得读取其他 `run_id` 的数据。
> - 全部状态迁移采用六状态模型（含 `HUMAN_REVIEW_REQUIRED`），见 [`orchestration/STATE_MACHINE.md`](../orchestration/STATE_MACHINE.md)。
> - 涉及 Gate 判定的依赖，Gate 结果为 `PASS`/`CONDITIONAL`/`REJECT`/`HUMAN_REVIEW_REQUIRED` 四选一；`REJECT` 触发返工，同一 `issue_id` 最多 2 次自动返工，第 3 次未通过转 `HUMAN_REVIEW_REQUIRED`（见 [`orchestration/ORCHESTRATOR_RULES.md`](../orchestration/ORCHESTRATOR_RULES.md) 第 5 节）。
> - **Gate（Schema Gate / Data Gate / Insight Gate）不是 Agent**，不计入本文件的 13 个角色，也不出现在下方的逐项档案中；它是独立、确定性、可审计的规则模块，档案见 [`gates/`](../gates/)。

---

## 1. Supervisor Agent

- **Department**: 治理层
- **Layer**: L0
- **Wave**: W0（启动），并在每个 Wave 结束后持续重扫（跨 Wave）
- **Dependencies**: 无（流程发起者）
- **Inputs**: Agent 注册表、依赖图、本次 run 的预期数据源清单、Gate 规则表、当前 `run_id`
- **Tools**: 编排状态存储（Agent 状态登记表，按 `run_id` 隔离）；不直接处理业务数据
- **Responsibilities**: 扫描 Agent 依赖、派发任务、原样执行三道 Gate 的判定结果、执行返工上限规则、处理 `FAILED`/`HUMAN_REVIEW_REQUIRED` 传播、每个 Wave 结束后重扫全部未运行 Agent
- **Authority**: 变更 Agent 状态（`BLOCKED↔READY`、`COMPLETED→READY`/`HUMAN_REVIEW_REQUIRED`）、按 Gate 既定规则放行/阻断下游
- **Forbidden**: 不得修改任何 Artifact 内容；不得代替专业 Agent 做业务判断；不得代替 Critic 做质疑；不得修改 Gate 结论；不得在第 3 次 REJECT 后继续自动返工；不得自行将 `HUMAN_REVIEW_REQUIRED` 迁移回 `READY`
- **Artifacts**: 派发与状态变更记录（由 Knowledge Agent 落盘，不单独产出业务 Artifact）
- **Completion Criteria**: 全流程持续存在，直至 Action Agent `COMPLETED` 且三道 Gate 均已正确执行
- **Failure Conditions**: 出现无法解开的依赖死锁；某 Gate 长期无法判定
- **Downstream Consumers**: 全部 13 个 Agent（调度对象）；Knowledge Agent（记录调度决策）

---

## 2. Knowledge Agent

- **Department**: 治理层
- **Layer**: L0
- **Wave**: 跨 Wave 持续运行（W0–W10），`run_log.md` 在 Action Agent `COMPLETED` 后定稿
- **Dependencies**: 无（被动记录者），但最终完整日志依赖全流程结束
- **Inputs**: 每个 Agent 的任务定义、输入、读取的 Artifact、状态变化（含 `HUMAN_REVIEW_REQUIRED`）、Gate 判定（四态）、Critic 结果、返工记录（`issue_id`/`reject_reason`/`retry_count`/`responsible_agent`/`previous_artifact`/`revised_artifact`/`previous_conclusion`/`revised_conclusion`）、耗时、最终产出。对 Data Intake Agent 额外记录：开始/结束时间、输入文件、`inspect_excel.py` 调用情况、`source_id` 分配、`MISSING`/`UNREADABLE` 情况
- **Tools**: 只追加式日志存储，按 `run_id` 隔离
- **Responsibilities**: 见 [`agents/knowledge.md`](../agents/knowledge.md) 全量清单
- **Authority**: 只读全部 Agent 的状态与 Artifact 元数据；只写 `runs/{run_id}/logs/run_log.md`
- **Forbidden**: 不得修改业务结论；不得替 Supervisor 放行；不得替 Critic 做业务质疑；不得替专业 Agent 完成任务；不得跨 `run_id` 混写日志
- **Artifacts**: `run_log.md`（持续更新）
- **Completion Criteria**: `run_log.md` 完整反映流程终态（含所有返工的 7 项必录字段与最终结果）
- **Failure Conditions**: 无法读取某 Agent 的状态/Artifact 元数据 → 记录 `INSUFFICIENT_EVIDENCE`，不阻塞主流程
- **Downstream Consumers**: Supervisor（审计）、人工复核者（`HUMAN_REVIEW_REQUIRED` 案例处理）

---

## 3. Data Intake Agent

- **Department**: 数据治理部
- **Layer**: L1
- **Wave**: W1（与 Academic Context Agent 并行，二者互不依赖）
- **Dependencies**: 无（起点，直接面对本次 run 的原始输入文件）
- **Inputs**: `runs/{run_id}/input/` 下本次 run 实际存在的原始 Excel 文件；本次 run 的预期数据源清单（由运行配置提供）
- **Tools**: `scripts/data/inspect_excel.py`（确定性文件扫描工具，本阶段不实现代码）
- **Responsibilities**: 登记应收数据源、核对实际收到的数据源、为每个数据源分配 `source_id`、确认年份/部门/文件/Sheet/可读性、调用 `inspect_excel.py` 生成真实结构 Profile、标记 `RECEIVED`/`MISSING`/`UNREADABLE`/`PARTIAL`/`UNKNOWN`、形成 `source_manifest.json`、把真实 Profile（非业务解释）交给 Schema Mapping Agent
- **Authority**: 分配 `source_id`；基于确定性扫描结果判定数据源状态
- **Forbidden**: 不判断字段业务语义；不建立 Schema Mapping；不标准化字段值；不清洗数据；不判断历史需求规律；不修改任何原始文件；不得凭文本描述代替真实文件扫描
- **Artifacts**: `source_manifest.json`、`source_profiles/source_{NNN}.json`
- **Completion Criteria**: 见 [`agents/data_intake.md`](../agents/data_intake.md) 的 8 条完整标准；核心是"全部文件均登记、无静默遗漏、`source_manifest` 数量可核对"，**不要求全部数据源均 `RECEIVED`**——缺失/不可读只需如实标记
- **Failure Conditions**: `runs/{run_id}/input/` 目录本身不可访问，或 `inspect_excel.py` 调用机制完全失效 → `FAILED`。部分文件缺失/不可读不构成 `FAILED`，属于登记工作的正常产出范围
- **Downstream Consumers**: Schema Mapping Agent、Schema Gate、Knowledge Agent

---

## 4. Schema Mapping Agent

- **Department**: 数据治理部
- **Layer**: L1
- **Wave**: W2
- **Dependencies**: Data Intake Agent `COMPLETED`
- **Inputs**: `source_manifest.json`、`source_profiles/*.json`（**不再直接读取原始 Excel 文件**——原始文件的结构扫描已由 Data Intake Agent 完成）
- **Tools**: 确定性结构比对工具（Python/pandas 类，本阶段不实现代码）
- **Responsibilities**: 基于 Data Intake Agent 提供的真实结构 Profile，识别各数据源字段的业务含义，建立到统一标准字段的映射；对无法确定含义的字段显式标记 `UNKNOWN` 并说明原因
- **Authority**: 定义标准字段命名空间；对不可映射字段标记 `UNKNOWN`
- **Forbidden**: 不得修改原始文件；不得在证据不足时臆测字段含义；不得执行合并/清洗（属 Data Standardization Agent）；不得重新扫描或质疑 Data Intake Agent 的结构性 Profile（若 Profile 本身有误，应通过 Schema Gate REJECT 回退给 Data Intake Agent，而非自行改写）
- **Artifacts**: `schema_mapping.json`
- **Completion Criteria**: 每个 `RECEIVED` 数据源的每个列均已映射到标准字段，或显式标记 `UNKNOWN` 并附原因
- **Failure Conditions**: `source_manifest.json`/`source_profiles` 完全不可用，导致无法进行任何映射 → `FAILED`；同一 `issue_id` 被 Schema Gate 连续 REJECT 达 3 次 → `HUMAN_REVIEW_REQUIRED`
- **Downstream Consumers**: Data Standardization Agent、Schema Gate、Knowledge Agent

---

## 5. Data Standardization Agent

- **Department**: 数据治理部
- **Layer**: L1
- **Wave**: W3（需 Schema Gate `PASS`/按规则 `CONDITIONAL` 后）
- **Dependencies**: Schema Mapping Agent `COMPLETED` + Schema Gate `PASS`/`CONDITIONAL`（按规则允许）
- **Inputs**: `schema_mapping.json`、原始数据源文件（路径来自 `source_manifest.json` 中各 `source` 的 `file_path`）
- **Tools**: 确定性合并/去重/日期转换工具（Python 类，本阶段不实现代码）
- **Responsibilities**: 按映射统一字段名/类型/日期格式/单位；合并各数据源；去重；保持原始数据不可覆盖；记录每条清洗规则以便追溯
- **Authority**: 创建标准化数据集；定义 `standardization_rules.json`
- **Forbidden**: 不得覆盖/修改原始文件；不得静默丢弃记录；不得做质量判断（属 Data Quality Agent）
- **Artifacts**: `standardization_rules.json`、`unified_dataset.xlsx`
- **Completion Criteria**: 产出覆盖全部 `RECEIVED` 数据源的统一数据集，且规则可追溯
- **Failure Conditions**: 映射不足以标准化某必需字段；结构冲突无法调和 → `FAILED`。同一 `issue_id` 被 Data Gate 连续 REJECT 达 3 次 → `HUMAN_REVIEW_REQUIRED`
- **Downstream Consumers**: Data Quality Agent、Knowledge Agent

---

## 6. Data Quality Agent

- **Department**: 数据治理部
- **Layer**: L1
- **Wave**: W4
- **Dependencies**: Data Standardization Agent `COMPLETED`
- **Inputs**: `unified_dataset.xlsx`、`standardization_rules.json`
- **Tools**: 确定性统计/校验工具（Python 类，本阶段不实现代码）
- **Responsibilities**: 审核完整性、重复率、空值/异常值率、日期有效性、跨表一致性；给出量化的 `PASS`/`CONDITIONAL`/`REJECT` 建议，供 Data Gate 直接核查使用
- **Authority**: 提出数据集是否达到"可信统一历史数据集"标准的量化依据（最终判定权在 Data Gate）
- **Forbidden**: 不得修改数据集内容；不得自行放行 Data Gate
- **Artifacts**: `quality_report.json`
- **Completion Criteria**: 报告含量化指标与明确结论
- **Failure Conditions**: 因数据缺失无法计算必需质量指标 → `FAILED`
- **Downstream Consumers**: Data Gate、Historical Demand Pattern Agent、Knowledge Agent

---

## 7. Historical Demand Pattern Agent

- **Department**: 历史与情报部
- **Layer**: L2
- **Wave**: W5（需 Data Gate `PASS`/按规则 `CONDITIONAL` 后）
- **Dependencies**: Data Quality Agent `COMPLETED` + Data Gate `PASS`/`CONDITIONAL`（按规则允许，且预测目标月份同期数据本身绝不允许 `CONDITIONAL`）
- **Inputs**: `unified_dataset.xlsx`（Data Gate 通过版本）、`quality_report.json`、预测目标月份参数
- **Tools**: 确定性统计工具（Python 类，本阶段不实现代码）
- **Responsibilities**: 分析预测目标月份过去三年同期（如预测 2026 年 8 月，使用 2023/2024/2025 年 8 月数据）的历史需求规律，产出量化统计结果
- **Authority**: 定义"历史同期规律"的量化口径，并附数据来源
- **Forbidden**: 不得以预测时点之前的最新走势作为主要依据；不得自行给出未来预测；不得查询学业节点
- **Artifacts**: `historical_pattern_report.json`
- **Completion Criteria**: 报告覆盖三年同期数据点，附统计结果与数据溯源
- **Failure Conditions**: 某一年或多年同期数据缺失/不足 → 标记 `UNKNOWN`/`INSUFFICIENT_EVIDENCE`；三年数据全部缺失 → `FAILED`
- **Downstream Consumers**: Current Context Validation Agent、Demand Insight Agent、Knowledge Agent

---

## 8. Academic Context Agent

- **Department**: 历史与情报部
- **Layer**: L2
- **Wave**: W1（与 Data Intake Agent 并行，不依赖内部数据管线）
- **Dependencies**: 无（只需预测目标年月参数）
- **Inputs**: 预测目标年月、学校官方网站
- **Tools**: 面向官方来源的信息查询（本阶段不实现代码，限定官方渠道）
- **Responsibilities**: 查询预测目标月份、目标年份的学校官方学业节点，记录来源 URL 与获取时间
- **Authority**: 只有来自学校官方渠道的信息才能被认定为"官方学业节点"
- **Forbidden**: 不得使用非官方/二手来源作为主要依据；不得判断业务影响；不得触碰历史数据
- **Artifacts**: `academic_context_report.json`
- **Completion Criteria**: 报告列出目标月份的官方学业节点及来源 URL；查不到的节点显式标记 `UNKNOWN`/`INSUFFICIENT_EVIDENCE`
- **Failure Conditions**: 官方来源完全不可达且无法获得任何节点信息 → 标记 `INSUFFICIENT_EVIDENCE`（部分缺失时仍可 `COMPLETED`）；完全无法访问 → `FAILED`
- **Downstream Consumers**: Current Context Validation Agent、Knowledge Agent

---

## 9. Current Context Validation Agent

- **Department**: 验证与洞察部
- **Layer**: L3
- **Wave**: W6
- **Dependencies**: Historical Demand Pattern Agent `COMPLETED` + Academic Context Agent `COMPLETED`
- **Inputs**: `historical_pattern_report.json`、`academic_context_report.json`
- **Tools**: 确定性比对逻辑（本阶段不实现代码）
- **Responsibilities**: 判断历史同期规律在今年是否仍然适用；近期业务走势只能作为可选校正信号引用
- **Authority**: 给出 `APPLICABLE`/`PARTIALLY_APPLICABLE`/`NOT_APPLICABLE`/`UNKNOWN` 判定，并附证据引用
- **Forbidden**: 不得直接生成需求洞察；不得在缺少来源引用时下结论；不得把近期走势当作主要依据
- **Artifacts**: `validation_report.json`
- **Completion Criteria**: 产出明确适用性判定及证据链接
- **Failure Conditions**: 两个输入均为 `UNKNOWN`/`INSUFFICIENT_EVIDENCE` → 整体标记 `UNKNOWN`
- **Downstream Consumers**: Demand Insight Agent、Knowledge Agent

---

## 10. Demand Insight Agent

- **Department**: 验证与洞察部
- **Layer**: L3
- **Wave**: W7（Critic REJECT 后重新进入本 Wave 返工，受返工上限约束）
- **Dependencies**: Current Context Validation Agent `COMPLETED`
- **Inputs**: `validation_report.json`、`historical_pattern_report.json`、`academic_context_report.json`；返工时额外输入上一轮 `critic_report.json` 的 `rework_instruction`
- **Tools**: 确定性综合（本阶段不实现代码）
- **Responsibilities**: 综合上述输入形成具体需求洞察，每条结论必须可追溯到证据
- **Authority**: 起草洞察；不具最终效力，需 Critic PASS
- **Forbidden**: 不得给出 7/14/28 天的具体预测数字；不得自我认定通过；不得输出无证据支撑的结论
- **Artifacts**: `insight_report.json`（每轮返工递增版本号）
- **Completion Criteria**: 每条洞察均关联到证据 Artifact ID
- **Failure Conditions**: 证据不足以支撑任何洞察 → 标记 `UNKNOWN`/`INSUFFICIENT_EVIDENCE`。同一 `issue_id`（某条洞察）被 Critic 连续 REJECT 达 3 次 → 该 Agent 状态转 `HUMAN_REVIEW_REQUIRED`
- **Downstream Consumers**: Critic Agent、Knowledge Agent

---

## 11. Critic Agent

- **Department**: 质疑与预测部
- **Layer**: L4
- **Wave**: W8
- **Dependencies**: Demand Insight Agent `COMPLETED`
- **Inputs**: `insight_report.json` 及其引用的全部上游 Artifact
- **Tools**: 确定性证据核对（本阶段不实现代码）
- **Responsibilities**: 逐条质疑洞察（业务推理层面），核实所引证据是否真实支撑结论；对每条及整体给出 `PASS`/`REJECT`；`REJECT` 需附稳定 `issue_id`、`reason`、`rework_instruction`
- **Authority**: `REJECT` 触发 Demand Insight Agent 返工（受 2 次自动返工上限约束）；`PASS` 是 Insight Gate 判定的输入之一
- **Forbidden**: 不得修改洞察内容本身；不得执行预测；不得在无法核实证据链时默认 `PASS`；不得与 Insight Gate 的结构性职责混淆
- **Artifacts**: `critic_report.json`（每轮审核版本化）
- **Completion Criteria**: 对每条结论给出明确 `PASS`/`REJECT` 及理由，覆盖全部条目
- **Failure Conditions**: 证据 Artifact 完全不可读，无法进行任何核实 → 该轮审核 `FAILED`
- **Downstream Consumers**: Insight Gate、Demand Insight Agent（`REJECT` 时）、Forecast Agent（`PASS` 且 Insight Gate 放行时）、Knowledge Agent

---

## 12. Forecast Agent

- **Department**: 质疑与预测部
- **Layer**: L4
- **Wave**: W9（需 Insight Gate `PASS`/按规则 `CONDITIONAL` 后）
- **Dependencies**: Critic Agent `PASS` + Insight Gate `PASS`/`CONDITIONAL`（按规则允许）
- **Inputs**: Critic 通过版本的 `insight_report.json`、`historical_pattern_report.json`、`validation_report.json`
- **Tools**: 确定性预测计算工具（Python 类，**本阶段不实现预测代码**）
- **Responsibilities**: 基于已通过审核的洞察，产出未来 7/14/28 天重点需求预测；`CONDITIONAL` 放行时同步标注对应窗口的不确定性风险标记
- **Authority**: 定义 `forecast_report.json` 的结构与取值
- **Forbidden**: 不得绕开 Critic 通过的洞察另起依据；不得引入未经验证的新数据源
- **Artifacts**: `forecast_report.json`
- **Completion Criteria**: 7/14/28 天预测均已产出，且每项可追溯至已通过的洞察条目
- **Failure Conditions**: 已通过洞察不足以支撑某一时间窗口的预测 → 该窗口标记 `UNKNOWN`/`INSUFFICIENT_EVIDENCE`
- **Downstream Consumers**: Action Agent、Knowledge Agent

---

## 13. Action Agent

- **Department**: 行动输出部
- **Layer**: L5
- **Wave**: W10
- **Dependencies**: Forecast Agent `COMPLETED`
- **Inputs**: `forecast_report.json`
- **Tools**: 确定性"预测→动作类别"映射（本阶段不实现代码）
- **Responsibilities**: 将预测转化为具体的销售/运营/业务准备动作，每条动作可追溯到具体预测条目
- **Authority**: 定义 `action_plan.md` 的内容结构
- **Forbidden**: 不得修改预测数值；不得添加与预测无关的臆测性动作
- **Artifacts**: `action_plan.md`（落盘于 `runs/{run_id}/final/`）
- **Completion Criteria**: 动作方案覆盖全部预测时间窗口，且逐条可追溯
- **Failure Conditions**: `forecast_report.json` 缺少必需窗口 → 对应窗口的动作标记 `UNKNOWN`
- **Downstream Consumers**: 销售/运营团队（最终使用者）、Knowledge Agent（最终日志定稿）
