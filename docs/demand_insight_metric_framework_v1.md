# Demand Insight Metric Framework V1.0

This is the frozen calculation contract for the historical Demand Insight stage. The machine-readable source is [`config/insight/demand_insight_metrics_v1.yaml`](../config/insight/demand_insight_metrics_v1.yaml).

## Scope

The current evidence consists only of the August cohorts for 2023, 2024, and 2025. All comparison is therefore “2023–2025 年 8 月同期需求对比”; it is not a full-year trend or a seasonal forecast.

## Fixed dimensions and value labels

V1 analyzes `year`, `country`, `school`, `degree_level`, `task_type`, `ddl`, and `channel`. `department` remains provenance only. Customer value labels are `customer_group` from `channel_group`, key-account business (`学年包` / `毕业无忧` / `DP`), and high-value transactions (`amount_cny > 10000`). High value is not customer LTV.

## Calculation safeguards

Each artifact writes its own denominator and definition. School ranking uses eligible canonical-school records; named secondary channels exclude legal null secondary channels; DDL uses parseable dates; task-type counts expand frozen MULTI_TASK components. MULTI_TASK amounts are never allocated across components. Course fields are deferred pending completeness, standardization, correspondence, and cross-year consistency checks.

## Output layers

`overall/` contains the combined August-cohort profile; `2023/`, `2024/`, and `2025/` contain annual August profiles; `trend/` contains same-period comparisons; `key_account/` and `high_value/` contain business-value views. Metric QA validates consistency before the framework is considered frozen.
