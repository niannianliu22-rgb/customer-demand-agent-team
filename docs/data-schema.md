# Canonical Data Schema — v1.2.0

[`schemas/canonical_schema.json`](../schemas/canonical_schema.json) 是 `unified_dataset` 的唯一正式字段定义。本文件与 JSON 同步说明；若发生冲突，以 JSON 为准。Data Standardization、Data Quality、Data Gate、下游 Agent 和 Python 脚本只能读取或输出其中列出的字段，禁止自行新增同义列。

## Frozen field groups

| 分组 | 正式字段 |
|---|---|
| 来源追溯 | `source_id`, `source_file`, `source_sheet`, `source_row_id`, `year`, `department` |
| 客户/需求 | `consultation_date_original`, `consultation_date`, `country_original`, `country`, `school_original`, `school`, `country_school_conflict`, `degree_level_original`, `degree_level`, `major`, `task_type`, `ddl_original`, `ddl`, `channel_original`, `channel_group`, `channel`, `channel_rule_id`, `channel_rule_version`, `channel_standardization_status` |
| 订单 | `order_id`, `order_status`, `consultant_name` |
| 金额 | `amount_original`, `currency_original`, `amount_cny` |

`source_id`、`source_file`、`source_sheet`、`source_row_id`、`year`、`department` 为每一业务记录必填。其余字段是否允许为空由源数据与质量规则判定；不得为了填满字段而臆造值。

## Explicit legacy-to-final mapping

| 上游 Mapping 语义名 / 旧名 | 最终 unified_dataset 字段 | 说明 |
|---|---|---|
| `deadline` | `ddl`、`ddl_original` | `deadline` 仅为 Schema Mapping 的旧语义标签，不能作为最终列名。 |
| `amount` | `amount_original`、`currency_original`、`amount_cny` | `amount` 是逻辑映射组，不是最终正式列。 |
| `date_original` | `consultation_date_original` 或 `ddl_original` | 按原始日期所属业务字段保留。 |
| `date_standardized` | `consultation_date` 或 `ddl` | 按标准化日期所属业务字段输出。 |

RULE-006 的“原始值与标准化值并存”要求按字段实现：咨询日期使用 `consultation_date_original` / `consultation_date`，截止日期使用 `ddl_original` / `ddl`。这只冻结派生数据集列名，不修改 Business Rules 内容。

## Amount contract

最终数据集禁止单一 `amount` 列：

- AUD：`amount_original` 保留原值，`currency_original="AUD"`，`amount_cny=amount_original*4.5`，按 RULE-009 四舍五入两位。
- CNY：`amount_original` 保留原值，`currency_original="CNY"`，`amount_cny=amount_original`，按 RULE-010 不换算。

## School entity contract

RULE-013 与 [`config/data/school_aliases.yaml`](../config/data/school_aliases.yaml) 定义学校实体：`school_original` 永远保留原始值，`school` 写入人工确认的 canonical 名称。`/` 写为 `NON_SCHOOL`、`未知` 写为 `UNKNOWN`，二者不得参与学校排名。保留 `country_original`；与字典 `canonical_country` 不一致时只写 `country_school_conflict=COUNTRY_SCHOOL_CONFLICT`，本阶段不改写 country。

## Channel contract

RULE-028 与 [`config/dimensions/channel/channel_rules_frozen_v1.yaml`](../config/dimensions/channel/channel_rules_frozen_v1.yaml) 定义 Channel v1.0：`channel_original` 永远保留输入原始值；`channel_group` 仅为「老客户」或「新客户」；`channel` 为冻结二级 canonical 渠道。原始值「新客户」可合法写为 `channel_group=新客户` 与 `channel=null`，表示历史数据未记录具体获客来源；该空值不归因到任何命名获客渠道，且「未知来源」不是 canonical channel。

## Excluded fields

「跟进反馈」「客户备注」「未成交原因」由 RULE-011 排除，不得进入 `unified_dataset`；这不授权删除或改写原始 Excel。

## Change control

Schema 已冻结为 `1.2.0`。任何字段新增、删除、重命名、类型或标准化语义变化都必须创建新 schema version，并同步更新 Data Standardization、Data Quality、Data Gate 与数据产品版本；不得在 v1 中静默变更。
# Schema V1.5 controlled compatibility update

Schema V1.5.0 adds nullable `school_id` as the stable key for an approved canonical school mapping. It is a join/traceability key, not a new default analysis dimension.

# Schema V1.4 controlled compatibility update

Schema V1.4.0 adds `school_rule_id`, `school_rule_version`, `school_standardization_status`, and `ddl_components` as standardization metadata/lineage fields. `ddl_components` retains every confirmed ISO date from a multi-DDL source, while `ddl` holds its earliest confirmed date for existing single-date consumers.

# Schema V1.3 controlled compatibility update

Schema V1.3.0 formally registers six existing Frozen Task Type v17 lineage/audit fields: `task_type_original`, `task_type_mode`, `task_type_components`, `task_type_rule_id`, `task_type_rule_version`, and `task_type_standardization_status`. They are standardization metadata/lineage fields, not business-analysis dimensions, and are therefore not default inputs to Monthly Demand Opportunity analysis.
