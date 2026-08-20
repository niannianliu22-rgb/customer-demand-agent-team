# DATA GATE

> 位置：Data Quality Agent 之后，Historical Demand Pattern Agent 之前。把关对象：统一历史数据集是否达到"可信统一历史数据集"的标准。
>
> **Gate 的性质**：独立、确定性、可审计的规则模块，不是 Agent。判定结果为四选一：`PASS` / `CONDITIONAL` / `REJECT` / `HUMAN_REVIEW_REQUIRED`。Supervisor 只能原样执行，无权自行改判（见 [`orchestration/ORCHESTRATOR_RULES.md`](../orchestration/ORCHESTRATOR_RULES.md) 第 6、7 节）。

> **发布边界**：本 Gate 不生成数据产品，但其结果是唯一发布依据。`PASS` 才允许确定性发布器将已验收的统一数据集发布为 `data/processed/` stable 产品；`CONDITIONAL` 只允许发布至 `data/processed/candidate/` 且标记 `release_status=CONDITIONAL`；`REJECT` / `HUMAN_REVIEW_REQUIRED` 禁止任何 processed 发布。

## Directly-Inspected Artifacts（Gate 必须直接读取的真实证据）

Data Quality Agent 产出 `quality_report.json`，但 Data Gate **不得只读取该报告的文字结论**，必须直接检查：

- `unified_dataset.xlsx`（统一数据集本身——实际行数、字段取值分布、日期范围）
- `quality_report.json`（Data Quality Agent 的量化指标与结论）
- `standardization_rules.json`（cleaning log，用于核实报告中指出的问题是否能对应到具体规则条目，含 RULE-001、RULE-002～006 的应用记录）
- `policies/business_rules.md` / `config/data/standardization_rules.yaml`（`rules_version: "3.0"`，用于核实 Data Quality Agent 的统计口径是否正确应用了 RULE-001、RULE-006、RULE-009、RULE-010、RULE-011、RULE-012、RULE-013）
- `schemas/canonical_schema.json`（冻结的 `unified_dataset` 正式字段名、类型与禁止同义列约束）
- `config/data/school_aliases.yaml`（RULE-013 ACTIVE 学校实体字典及 canonical_country）
- 相关源数据追溯信息（`unified_dataset.xlsx` 中记录到 `source_manifest.json` 各 `source` 的行级溯源引用，用于抽样核实统一数据集的记录确实可追溯回某个原始数据源的某些行，而非报告单方面声称）

## Check Items

1. **完整性指标**：统一数据集是否覆盖全部 `RECEIVED` 数据源的数据量级，缺失部分有说明。
2. **重复率**：去重后是否仍存在明显重复记录。
3. **空值/异常值率**：关键字段（日期、部门、需求/订单量）的空值率与异常值率是否在 `quality_report.json` 自行定义的合格阈值内，**且统计口径已按 RULE-001 排除整行空白记录**——若 Gate 抽样发现报告把整行空白行计入了缺失率分母，视为口径错误（见 DG-R5）。
4. **日期有效性**：`consultation_date` 与 `ddl` 是否落在合理范围内、年份是否与对应 `source` 的 `year` 一致（RULE-002～005）；`consultation_date_original` 与 `ddl_original` 是否完整保留（RULE-006）。
5. **跨表一致性**：同一标准字段在不同数据源合并后取值是否自洽。
6. **规则可追溯性**：`quality_report.json` 中指出的问题是否能对应到 `standardization_rules.json` 中的具体规则条目。
7. **溯源可验证性**：抽样核实 `unified_dataset.xlsx` 中的记录能否追溯回某个 `source` 的具体行。
8. **预测目标月份数据完整性**：本次 `run_id` 对应的预测目标月份，其过去三年同期数据（Historical Demand Pattern Agent 的核心输入）是否受到任何已识别质量问题的影响。
9. **已确认业务规则的应用正确性**：RULE-001（整行空白行不计入缺失率/样本量/Gate 风险判断）、RULE-002～005（日期解析模式，年份取 `source.year`）、RULE-006（每类日期的原始值/标准化值双字段保留，即 `consultation_date_original`/`consultation_date` 与 `ddl_original`/`ddl`）是否被 Data Standardization Agent 与 Data Quality Agent 正确、一致地应用。
10. **金额换算正确性（RULE-009/RULE-010）**：抽样核实 `currency_original="AUD"` 的记录，`amount_cny` 是否等于 `amount_original × 4.5`（两位小数舍入）；`currency_original="CNY"` 的记录，`amount_cny` 是否等于 `amount_original`（未发生换算）；核实汇率不是从任何实时/外部来源获取的（固定值 4.5 之外的任何数值即为违规）。
11. **排除字段合规性（RULE-011）**：核实 `unified_dataset.xlsx` 中确实不包含「客户备注」「跟进反馈」「未成交原因」（或其映射后的字段名）；同时核实原始 Excel 文件（`runs/{run_id}/input/`）中对应列未被删除或修改。
12. **学历枚举合规性（RULE-012）**：核实 `degree_level` 取值落在 `{本科, 硕士, 博士, 高中, UNKNOWN}` 内，大一/大二/大三/大四已正确归一为"本科"；核实 `degree_level_original` 完整保留。
13. **Canonical Schema Freeze 合规性**：核实 `unified_dataset.xlsx` 只使用 `canonical_schema.json` 中定义的字段，包含 6 个来源追溯字段，不含 `amount`、`deadline`、`date_original`、`date_standardized` 或其他未登记同义列；金额只能使用 `amount_original`、`currency_original`、`amount_cny`。
14. **学校实体与国家冲突合规性（RULE-013）**：核实 `school_original` 保留、`school` 仅使用 ACTIVE 字典 canonical 值或 `NON_SCHOOL`/`UNKNOWN`；后两者不进入学校排名；`COUNTRY_SCHOOL_CONFLICT` 被记录且 country 未被静默改写。
13. **发布就绪性**：仅在本 Gate 为 `PASS` 时，确认可发布来源是最终验收的 `unified_dataset.xlsx`，并具备 `source_id`、`source_file`、`source_sheet`、`source_row_id`、`year`、`department` 六个行级追溯字段；发布器必须保留本 Gate 状态、规则版本、质量指标和 Artifact 引用。

## Decision Rule Table

| Rule ID | 触发条件 | 判定 | 允许继续到的下游 | 必须携带的风险标记 |
|---|---|---|---|---|
| DG-P1 | 关键字段完整性、重复率、空值率、日期有效性均达标；无跨表一致性冲突；溯源抽样核实通过；`quality_report.json` 结论为 `PASS` | `PASS` | Historical Demand Pattern Agent | 无 |
| DG-C1 | 存在**非关键字段**或**预测目标月份同期数据范围之外**的小范围质量问题，`quality_report.json` 结论为 `CONDITIONAL`，且问题已对应到具体规则条目 | `CONDITIONAL` | Historical Demand Pattern Agent | `risk_flag: DATA_QUALITY_MINOR_ISSUE_OUTSIDE_TARGET_SCOPE`，需列出受影响字段/记录范围 |
| DG-R1 | 关键字段（日期、部门、需求/订单量）完整性或准确性不达标 | `REJECT` | 无 | — |
| DG-R2 | 预测目标月份相关的历史同期数据（Historical Demand Pattern Agent 的核心输入）存在质量问题 | `REJECT` | 无 | — |
| DG-R3 | 报告结论为 `REJECT`，或报告/数据集结构不符合契约 | `REJECT` | 无 | — |
| DG-R4 | 抽样溯源核实失败（`unified_dataset.xlsx` 中的记录无法追溯回某个 `source`） | `REJECT` | 无 | — |
| DG-R5 | RULE-001、RULE-002～006 被错误应用或未应用（如缺失率把整行空白行计入分母、日期标准化丢失 `consultation_date_original` 或 `ddl_original`、年份未取自对应 `source.year`） | `REJECT` | 无 | — |
| DG-R6 | RULE-009 被错误应用（汇率非固定 4.5，或疑似调用了实时汇率） | `REJECT` | 无 | — |
| DG-R7 | RULE-011 未被正确执行（`unified_dataset` 中残留应被排除的字段） | `REJECT` | 无 | — |
| DG-R8 | RULE-012 应用错误（`degree_level` 出现枚举外取值且未标记 `UNKNOWN`，或大一～大四未被归一为"本科"，或 `degree_level_original` 缺失） | `REJECT` | 无 | — |
| DG-R9 | 违反 Canonical Schema Freeze（缺少必需追溯字段、出现未登记同义字段、仍输出 `amount`/`deadline`，或未按三列金额结构输出） | `REJECT` | 无 | — |
| DG-R10 | RULE-013 未正确应用（学校 alias 未按 ACTIVE 字典处理、非学校值进入排名、未保留 `school_original`，或 country 被静默改写） | `REJECT` | 无 | — |

## Never-Conditional（绝不能 CONDITIONAL 的情形）

- 预测目标月份同期数据本身存在质量问题——**无论问题大小**，只要落在 Historical Demand Pattern Agent 将直接使用的数据范围内，一律 `REJECT`，不得以风险标记方式放行（这是本 Gate 相较上一版最重要的收紧点：CONDITIONAL 不等于 PASS，目标月份数据是核心依据，不容许"带瑕疵将就使用"）；
- 溯源核实失败——数据无法追溯即违反 Evidence First 原则，只能 `REJECT`；
- 已确认业务规则（RULE-001、RULE-002～006、RULE-009、RULE-010、RULE-011、RULE-012）被错误应用——这类错误会系统性扭曲质量指标本身的可信度，只能 `REJECT`，不得以风险标记方式放行；
- 汇率使用错误（非固定 4.5）——这是财务口径的硬性合规问题，不属于"可接受风险"。

## HUMAN_REVIEW_REQUIRED

若质量问题的"是否属于预测目标月份范围""是否达到规则阈值"等判定无法依据 DG-P1/DG-C1 或 DG-R1～DG-R8 明确归类（例如问题恰好处于阈值边界、或影响范围的判定存在歧义），Gate 输出 `HUMAN_REVIEW_REQUIRED`，不得由 Supervisor 主观归类。

## Downstream Impact

- **PASS / CONDITIONAL（按命中规则）**：Historical Demand Pattern Agent 的 Gate 依赖条件满足；`CONDITIONAL` 的风险标记需随链路透传，Historical Demand Pattern Agent 在报告中需引用该标记并保持谨慎。
- **数据产品发布**：`PASS` 时，在不覆盖已有版本的前提下，允许发布器生成 stable 产品包；`CONDITIONAL` 时只能生成 candidate 产品包；`REJECT` 与 `HUMAN_REVIEW_REQUIRED` 时禁止发布。发布规则与文件清单见 [`docs/DATA_PRODUCT_RELEASE.md`](../docs/DATA_PRODUCT_RELEASE.md)。
- **REJECT**：Historical Demand Pattern Agent 保持 `BLOCKED`；问题回退给 Data Standardization Agent（若源于标准化规则）或进一步回退给 Schema Mapping Agent（若源于字段映射），由问题定位决定回退层级；对应 Agent 进入返工流程（`issue_id` 计数，最多 2 次自动返工，第 3 次未通过转 `HUMAN_REVIEW_REQUIRED`）。
- **HUMAN_REVIEW_REQUIRED**：Historical Demand Pattern Agent 保持 `BLOCKED`；Data Quality Agent 状态维持 `COMPLETED`；等待人工补充判断或修订本 Gate 的规则表。
