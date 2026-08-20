# DATA PRODUCT RELEASE — 标准历史数据产品发布机制

## 1. 目的与存储边界

数据治理的运行证据与可复用数据产品必须分离：

| 位置 | 职责 | 是否可被其他项目直接消费 |
|---|---|---|
| `runs/{run_id}/artifacts/` | 本次运行的中间结果、审计证据与返工追溯 | 否；仅作为证据来源 |
| `data/processed/` | 已通过 Data Gate 的稳定标准历史数据产品 | 是 |
| `data/processed/candidate/` | Data Gate `CONDITIONAL` 的候选产品 | 仅可评估使用，非 stable |

发布只复制/导出派生数据；任何发布步骤均不得删除、覆盖或改写 `runs/{run_id}/input/` 中的原始 Excel。

## 2. 发布决策

发布器是 Data Gate 之后的确定性机制，不是新增 Agent，也不取代 Gate 的判定权。

| Data Gate 结果 | 发布位置 | `release_status` | 规则 |
|---|---|---|---|
| `PASS` | `data/processed/` | `STABLE` | 可发布正式数据产品 |
| `CONDITIONAL` | `data/processed/candidate/` | `CONDITIONAL` | 仅可发布候选产品；严禁写入 stable 路径 |
| `REJECT` | 不发布 | 不适用 | 不得产生任何 processed 数据产品 |
| `HUMAN_REVIEW_REQUIRED` | 不发布 | 不适用 | 不得产生任何 processed 数据产品 |

stable 发布还必须逐项满足：Data Intake `COMPLETED`、Schema Mapping `COMPLETED`、Schema Gate `PASS`、Data Standardization `COMPLETED`、Data Quality `COMPLETED`、Data Gate `PASS`。Schema Gate 的 `CONDITIONAL` 即使允许数据治理链路继续，也不能生成 stable 产品。

## 3. v1 产品包

当 stable 条件满足时，发布器从最终通过审核的 `unified_dataset.xlsx` 导出以下同版本产品：

```
data/processed/
  customer_demand_history_2023_2025_v1.xlsx
  customer_demand_history_2023_2025_v1.csv
  customer_demand_history_2023_2025_v1.metadata.json
  data_dictionary_v1.md
  cleaning_log_v1.json
  quality_report_v1.json
```

候选发布使用相同文件名与结构，但根目录固定为 `data/processed/candidate/`，metadata 中必须写 `release_status: "CONDITIONAL"` 与 Data Gate 风险标记。`cleaning_log_v1.json` 是已验收 `standardization_rules.json` 的发布副本；`quality_report_v1.json` 是 Data Gate 所检查的 `quality_report.json` 的发布副本，均不得被发布器改写业务结论。

主数据集只可由最终通过审核的 `unified_dataset.xlsx` 转换而来，必须含以下行级追溯字段：`source_id`、`source_file`、`source_sheet`、`source_row_id`、`year`、`department`，以及 Schema Mapping 定义的核心 canonical 字段。RULE-011 排除字段不得进入主表。

## 4. Metadata 契约

`customer_demand_history_2023_2025_v{N}.metadata.json` 至少包含：

```json
{
  "dataset_name": "customer_demand_history_2023_2025",
  "dataset_version": "v1",
  "release_status": "STABLE | CONDITIONAL",
  "created_at": "ISO-8601 timestamp",
  "source_run_id": "RUN-...",
  "source_years": [2023, 2024, 2025],
  "departments": ["..."],
  "source_count": 6,
  "row_count": 0,
  "column_count": 0,
  "business_rules_version": "2.0",
  "schema_version": "string",
  "data_gate_status": "PASS | CONDITIONAL",
  "quality_score": "number | null",
  "quality_metrics": {},
  "currency_policy": {"AUD_to_CNY_fixed_rate": 4.5, "CNY_passthrough": true},
  "date_policy": {"rules": ["RULE-002", "RULE-003", "RULE-004", "RULE-005", "RULE-006"], "year_source": "source.year"},
  "excluded_fields": ["客户备注", "跟进反馈", "未成交原因"],
  "source_artifacts": [],
  "checksum": {"algorithm": "sha256", "files": {}}
}
```

`source_artifacts` 至少引用本次 run 的 `source_manifest.json`、`schema_mapping.json`、`standardization_rules.json`、`unified_dataset.xlsx`、`quality_report.json` 及 Data Gate 结果。`checksum.files` 必须包含发布的 XLSX、CSV、metadata、字典、清洗日志与质量报告的 SHA-256 值。

## 5. 数据字典与清洗日志

`data_dictionary_v{N}.md` 必须逐字段记录：`field_name`、中文名称、业务定义、数据类型、是否必填、原始来源字段、标准化规则、示例值、是否允许 `UNKNOWN`。其中必须明确：

- `amount_original`：原始金额；保留原始收款数值。
- `currency_original`：原始币种；只允许 `AUD` 或 `CNY`。
- `amount_cny`：统一人民币金额；AUD 使用固定 4.5，CNY 保持原值。

v1 数据字典至少覆盖如下发布 Schema（部门特有字段可为非必填）：

| field_name | 中文名称 | 数据类型 | 是否必填 | 标准化规则 | 允许 `UNKNOWN` |
|---|---|---|---|---|---|
| `source_id` | 来源标识 | string | 是 | Data Intake 分配 | 否 |
| `source_file` | 来源文件 | string | 是 | 原始文件名保留 | 否 |
| `source_sheet` | 来源工作表 | string | 是 | 原始 Sheet 名保留 | 否 |
| `source_row_id` | 来源行号 | integer/string | 是 | 原始业务行定位 | 否 |
| `year` | 数据年份 | integer | 是 | source manifest 年份 | 否 |
| `department` | 部门 | string | 是 | source manifest 部门 | 否 |
| `date_original` | 原始日期 | string | 条件必填 | RULE-006 原样保留 | 是 |
| `date_standardized` | 标准日期 | date/string | 条件必填 | RULE-002～006 | 是，仅规则未覆盖时 |
| `country` | 意向国家 | string | 否 | canonical 映射 | 是 |
| `school` | 意向学校 | string | 否 | canonical 映射 | 是 |
| `degree_level_original` | 原始学历 | string | 否 | 原样保留 | 是 |
| `degree_level` | 学历层次 | string | 否 | RULE-012 | 是 |
| `major` | 专业/课程 | string | 否 | canonical 映射 | 是 |
| `deadline` | 截止日期 | date/string | 否 | 日期规则适用时保留原始/标准化追溯 | 是 |
| `task_type` | 作业/咨询类型 | string | 否 | RULE-008 仅字段级统一，不归类取值 | 是 |
| `channel` | 客户渠道/类型 | string | 否 | RULE-007 | 是 |
| `order_id` | 订单编号 | string | 否 | canonical 映射 | 是 |
| `amount_original` | 原始金额 | decimal | 否 | RULE-009/010 原始数值 | 是 |
| `currency_original` | 原始币种 | string | 否 | RULE-009/010，AUD/CNY | 否（存在金额时） |
| `amount_cny` | 统一人民币金额 | decimal | 否 | AUD×4.5；CNY 原值 | 是 |
| `order_status` | 订单状态 | string | 否 | canonical 映射 | 是 |
| `consultant_name` | 负责顾问/客服 | string | 否 | 顾问部特有字段 | 是 |

最终字典还必须为每个字段补全原始来源字段、业务定义和示例值；不能以本表代替这些发布时的必填信息。

`cleaning_log_v{N}.json` 必须是可量化、按规则可追溯的记录：字段重命名、值标准化、日期转换、金额换算、RULE-001 排除的整行空白数、RULE-011 排除字段、每条规则影响行数、`rule_id` 及 `business_rules_version`。不得以“清洗完成”代替明细。

`quality_report_v{N}.json` 必须保留通过 Gate 的质量审计结果，包括 source coverage、traceability coverage、missing metrics、duplicate metrics、invalid dates、amount anomalies、category consistency、warnings 与 known limitations。

## 6. 不可覆盖版本机制

`v1` 是首个发布版本。Business Rules、Schema、历史修正、来源范围或标准化口径任一发生变更时，必须发布新的 `v2`、`v3`……；既有版本及其 metadata/checksum 必须保留，不得覆盖。发布器在目标版本路径已存在时必须失败，不能覆盖已有文件。

## 7. 复用方式

推广中台、BI 或其他 Agent Team 只消费 `data/processed/` 的 `release_status: "STABLE"` 产品，并先读取同版本 metadata 和数据字典以取得字段、规则与血缘信息。候选产品必须显式接受 `CONDITIONAL` 风险后才能用于探索，不得作为正式指标、训练集或稳定下游输入。
