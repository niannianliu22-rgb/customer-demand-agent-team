# AGENT_RESPONSIBILITY — 责权边界与验收标准

> 本文件用「责（做什么）/ 权（可以决定什么）/ 边界（不能做什么，以及和相邻 Agent 的分界线）/ 验收标准（如何证明完成）」四要素，明确 12 个角色。与 [`AGENT_MAP.md`](AGENT_MAP.md) 互补。
>
> **通用说明（本版本新增）**：全部 Agent 的运行均限定在单一 `run_id` 范围内，不得跨 `run_id` 读取数据（见 [`docs/AGENT_CONTRACT.md`](AGENT_CONTRACT.md) 第 6 节）。全部返工循环（无论由 Gate 还是 Critic 触发）均受"同一问题最多 2 次自动返工"的上限约束，第 3 次未通过转 `HUMAN_REVIEW_REQUIRED`（见 [`orchestration/ORCHESTRATOR_RULES.md`](../orchestration/ORCHESTRATOR_RULES.md) 第 5 节）。

---

## 治理层

### Supervisor Agent

- **责**：调度全部 Agent；原样执行三道 Gate 的判定结果；执行返工上限规则；处理依赖、失败与 `HUMAN_REVIEW_REQUIRED` 传播；每个 Wave 结束后重扫。
- **权**：变更 Agent 状态（`BLOCKED↔READY`、`COMPLETED→READY`/`HUMAN_REVIEW_REQUIRED`）；决定何时终止/暂停流程。**不再拥有"判断 Gate 是否放行"的裁量权**——Gate 判定由 Gate 自身的预定义规则表得出，Supervisor 只是执行者。
- **边界**：不参与任何业务判断；不能替 Critic 质疑；不能替 Knowledge Agent 记录；不能替专业 Agent 完成任务；**不能凭主观判断把 REJECT 改成 CONDITIONAL 或 PASS，也不能在 Gate 输出 `HUMAN_REVIEW_REQUIRED` 时自行代为决定**；不能在第 3 次 REJECT 后继续自动放行返工。它只管"能不能跑，以及跑到第几次该停"，不管"跑得对不对"。
- **验收标准**：每个 Wave 结束后，所有满足依赖的 `BLOCKED` Agent 都已变为 `READY`；没有 Agent 被遗漏；三道 Gate 均被正确检查且结果被原样执行；返工上限规则被正确执行（同一 `issue_id` 第 3 次 REJECT 必转 `HUMAN_REVIEW_REQUIRED`，无一被违规多给一次机会）。

### Knowledge Agent

- **责**：记录任务、输入、读取的 Artifact、状态变化（含 `HUMAN_REVIEW_REQUIRED`）、Gate 四态判定、Critic 结果、返工的 7 项必录字段（`issue_id`/`reject_reason`/`retry_count`/`responsible_agent`/`previous_artifact`/`revised_artifact`/`previous_conclusion`/`revised_conclusion`）、耗时、最终产出；生成团队运行日志。
- **权**：对全部 Agent 状态与 Artifact 元数据有只读权限；对 `run_log.md`（`runs/{run_id}/logs/`）有唯一写权限。
- **边界**：不修改业务结论；不替 Supervisor 放行；不替 Critic 做业务质疑；不替专业 Agent 完成任务；不跨 `run_id` 混写。它是"记录者"而非"参与者"。
- **验收标准**：`run_log.md` 中每一条状态变化、每一次返工（含全部 7 项字段）、每一个最终产出都可与实际 Artifact 对应；无遗漏记录；缺字段的返工记录被显式标注为不完整，而非编造补全。

---

## 数据治理部

### Data Intake Agent

- **责**：回答"本次 run 实际收到的原始数据是什么，是否完整、可读、可登记"——登记预期数据源、核对实际数据源、分配 `source_id`、调用 `inspect_excel.py` 生成真实结构 Profile、标记每个数据源的收发状态。
- **权**：分配 `source_id`；基于 `inspect_excel.py` 的确定性扫描结果判定 `RECEIVED`/`MISSING`/`UNREADABLE`/`PARTIAL`/`UNKNOWN`。
- **边界**：不判断字段业务语义、不建立 Schema Mapping、不标准化字段值、不清洗数据、不判断历史需求规律、不修改原始文件——它只回答"这是什么数据、结构是什么"，绝不回答"这些字段代表什么业务含义"（那是 Schema Mapping Agent 的职责，见下一条）。不得凭文本描述代替真实文件扫描。
- **验收标准**：`source_manifest.json` 覆盖全部预期数据源（含缺失/不可读的）；每个数据源有唯一 `source_id`；每个可读文件有真实 `source_profile`；`expected_source_count`/`received_source_count` 与实际数量一致；无静默遗漏。**注意：`COMPLETED` 不要求数据源全部收齐**——缺失部分如实标记 `MISSING` 即可完成登记工作，是否允许流程继续由 Schema Gate 决定，不是 Data Intake Agent 自己判断。

### Schema Mapping Agent

- **责**：基于 Data Intake Agent 提供的真实结构 Profile，识别各数据源字段的业务语义，建立到标准字段的映射。
- **权**：定义标准字段命名空间；逐字段使用 `CONFIRMED`、`REVIEW_REQUIRED`、`UNMAPPED` 或 `EXCLUDED_BY_BUSINESS_RULE` 四态之一，并提供可核验映射依据。
- **边界**：不做合并、去重、日期转换；不做质量判断；不得修改原始文件；**不得自己重新扫描原始 Excel 文件或质疑 Data Intake Agent 的结构性 Profile**——若 Profile 本身有误（如列名扫描错误），应通过 Schema Gate REJECT 回退给 Data Intake Agent，而不是自行改写。与 Data Intake Agent 的分界线是：Data Intake 只记录"字段名叫什么、结构长什么样"（如"咨询时间、院校、任务、金额"），Schema Mapping 才能判断"这些字段业务上代表什么"（如"咨询时间 → `consultation_date`"）。与 Schema Gate 的分界线是——**它只产出映射结果，Gate 才有权判定该结果是否合格**（Gate 直接比对 `source_profiles` 中的实际列结构，不只信任本 Agent 的自述）。
- **验收标准**：`schema_mapping.json` 覆盖全部 `RECEIVED` 数据源的全部列；每列都有四态状态、具体原因与 `mapping_basis`/`evidence_refs`。`EXCLUDED_BY_BUSINESS_RULE` 必须引用 ACTIVE Rule，不能作为未映射的替代标记；若同一问题连续被 Schema Gate 拒绝达 2 次，第 3 次提交前必须针对 `rework_instruction` 做出实质性修改，否则触发 `HUMAN_REVIEW_REQUIRED`。

### Data Standardization Agent

- **责**：按映射统一字段、合并 6 表、去重、转换日期格式，保留可追溯的清洗规则。
- **权**：定义 `standardization_rules.json` 中的规则集。
- **边界**：不得覆盖原始文件；不评估数据是否"可信"（属 Data Quality Agent，且最终判定权在 Data Gate）；不重新定义字段映射。
- **验收标准**：`unified_dataset.xlsx` 覆盖全部 6 张源表数据；`standardization_rules.json` 中每条规则可追溯；原始文件未变；返工受 2 次上限约束。

### Data Quality Agent

- **责**：审核统一数据集的完整性、重复率、空值率、日期有效性、跨表一致性。
- **权**：给出量化的 `PASS`/`CONDITIONAL`/`REJECT` 结论，**作为 Data Gate 判定的输入之一**——Data Gate 会直接检查数据集、cleaning log、溯源信息本身，不会只采信本报告的文字结论。
- **边界**：不修改数据内容；**不拥有最终放行权**（放行权在 Data Gate，Data Gate 依据自己的 Decision Rule Table 判定，不是简单复述本报告结论）；不追溯重新判断字段映射。
- **验收标准**：`quality_report.json` 含量化指标与明确结论；结论有据可查；预测目标月份同期数据范围内的问题必须如实披露（不得淡化，因为该范围内任何问题在 Data Gate 都只能 REJECT，不能 CONDITIONAL）。

---

## 历史与情报部

### Historical Demand Pattern Agent

- **责**：分析预测目标月份过去三年同期的历史需求规律。
- **权**：定义同期规律的量化口径，并附数据来源。
- **边界**：只使用目标月份的同期历史数据作为主要依据；不产出未来预测；不涉及学业节点。
- **验收标准**：`historical_pattern_report.json` 覆盖三年同期数据点；每个统计结果标注数据来源与计算方法；缺失年份显式标记。

### Academic Context Agent

- **责**：查询预测目标年份、目标月份的学校官方学业节点。
- **权**：认定某信息为"官方学业节点"的前提是来源于学校官方渠道（见 [`policies/SOURCE_POLICY.md`](../policies/SOURCE_POLICY.md)）。
- **边界**：不使用非官方/二手来源作为主要依据；不判断学业节点对业务的影响；不涉及历史数据。
- **验收标准**：`academic_context_report.json` 中每个节点附来源 URL 与获取时间；无法确认的节点标记 `UNKNOWN`/`INSUFFICIENT_EVIDENCE`。

---

## 验证与洞察部

### Current Context Validation Agent

- **责**：判断历史同期规律在预测年份是否仍然适用。
- **权**：给出 `APPLICABLE`/`PARTIALLY_APPLICABLE`/`NOT_APPLICABLE`/`UNKNOWN` 判定。
- **边界**：只判断"规律是否适用"，不生成具体需求洞察；近期业务走势只能作为辅助校正信号。
- **验收标准**：`validation_report.json` 中的判定必须同时引用 `historical_pattern_report.json` 与 `academic_context_report.json` 的具体条目。

### Demand Insight Agent

- **责**：综合历史规律、官方学业节点、适用性判定，形成需求洞察。
- **权**：起草洞察条目，但不具备最终效力（需 Critic PASS + Insight Gate 结构性复核）。
- **边界**：不给出具体预测数字；不能自证通过；每条洞察必须能关联到证据 Artifact。
- **验收标准**：`insight_report.json` 中每条洞察都标注引用的证据 Artifact ID；返工后版本号递增；同一条洞察（`issue_id`）被 Critic 连续拒绝达 3 次，本 Agent 状态转为 `HUMAN_REVIEW_REQUIRED`，不得再自动重试。

---

## 质疑与预测部

### Critic Agent

- **责**：从**业务推理层面**质疑并核实 Demand Insight Agent 的每条结论——判断"这条洞察在逻辑上站不站得住、证据是否真正支撑其方向"。
- **权**：`REJECT` 可将 Demand Insight Agent 打回重做（受 2 次自动返工上限约束）；`PASS` 是 Insight Gate 判定的输入之一。
- **边界**：不修改洞察内容；不做预测；证据链无法核实时不得默认 `PASS`；**不承担 Insight Gate 的结构性/完整性核验职责**——Critic 关心"对不对"，Gate 关心"全不全、真不真、够不够格"，二者不得混淆（见 [`docs/AGENT_CONTRACT.md`](AGENT_CONTRACT.md) 第 5 节）。
- **验收标准**：`critic_report.json` 对每条洞察给出明确判定与理由，`REJECT` 项必须给出稳定 `issue_id` 与可执行的 `rework_instruction`。

### Forecast Agent

- **责**：基于 Critic 通过且 Insight Gate 放行的洞察，产出 7/14/28 天需求预测。
- **权**：定义预测结果结构与数值。
- **边界**：只能使用已通过 Insight Gate 的洞察作为依据；`CONDITIONAL` 放行的部分须同步保留不确定性标注。
- **验收标准**：`forecast_report.json` 覆盖 7/14/28 天三个窗口，每项预测可追溯到具体已通过的洞察条目。

---

## 行动输出部

### Action Agent

- **责**：将预测转化为销售、运营、业务准备动作。
- **权**：定义 `action_plan.md` 的内容结构与动作分类。
- **边界**：不修改预测数值；不添加与预测无关的臆测性动作。
- **验收标准**：`action_plan.md` 中每条动作都能追溯到 `forecast_report.json` 中的具体预测条目；覆盖全部有效预测窗口。
