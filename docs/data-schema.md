# Canonical Data Schema — v1.1.0

[`schemas/canonical_schema.json`](../schemas/canonical_schema.json) 是 `unified_dataset` 的唯一正式字段定义。本文件与 JSON 同步说明；若发生冲突，以 JSON 为准。Data Standardization、Data Quality、Data Gate、下游 Agent 和 Python 脚本只能读取或输出其中列出的字段，禁止自行新增同义列。

## Frozen field groups

| 分组 | 正式字段 |
|---|---|
| 来源追溯 | `source_id`, `source_file`, `source_sheet`, `source_row_id`, `year`, `department` |
| 客户/需求 | `consultation_date_original`, `consultation_date`, `country_original`, `country`, `school_original`, `school`, `country_school_conflict`, `degree_level_original`, `degree_level`, `major`, `task_type`, `ddl_original`, `ddl`, `channel` |
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

## Excluded fields

「跟进反馈」「客户备注」「未成交原因」由 RULE-011 排除，不得进入 `unified_dataset`；这不授权删除或改写原始 Excel。

## Change control

Schema 已冻结为 `1.1.0`。任何字段新增、删除、重命名、类型或标准化语义变化都必须创建新 schema version，并同步更新 Data Standardization、Data Quality、Data Gate 与数据产品版本；不得在 v1 中静默变更。
