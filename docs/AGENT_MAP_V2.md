# AGENT_MAP V2 — Fixed 13-Agent Registry

All outputs use the common envelope in `AGENT_CONTRACTS_V2.md`. Gates are not Agents.

| ID | Fixed Agent name | display_role | expanded_responsibility | Input | Output | Dependency / gate | Current implementation status |
|---|---|---|---|---|---|---|---|
| A01 | Supervisor Agent | Workflow Supervisor | Dispatch, state, return routing, gate execution and rescan. | Registry, workflow, states, gate results | state transitions; dispatch events | all workflow transitions | READY |
| A02 | Knowledge Agent | Evidence & Freeze Ledger | Append agent/rule/version/status/frozen/checksum/dependency/supersedes records. | events and artifact metadata | `run_log.jsonl`, frozen registry and run manifest | cross-cutting | READY |
| A03 | Data Intake Agent | Source Intake | Inventory and profile source files. | run input, expected sources | source manifest and profiles | SOURCE_GATE | READY |
| A04 | Schema Mapping Agent | Canonical Schema Mapper | Map profile columns to canonical fields. | manifest, profiles, frozen mapping rules | schema mapping | SCHEMA_GATE | READY |
| A05 | Data Standardization Agent | Dataset Standardizer | Standardize and preserve source lineage. | mapping, source data, rules | unified dataset, cleaning log, standardization rules | STANDARDIZATION_GATE | READY |
| A06 | Data Quality Agent | Dataset Quality Assurer | Produce formal quality decision evidence. | standardized dataset, cleaning log, schema, rules | `quality_report.json` | DATA_QUALITY_GATE | READY |
| A07 | Historical Demand Pattern Agent | Historical Demand Analysis | WHAT/VALUE/WHERE/WHEN historical evidence: inventory, pattern, value, market structure, lead time, August pattern and schools. | Data Quality Gate PASS dataset, target month, frozen historical rules | `historical_demand_report.json` | after DATA_QUALITY_GATE | READY |
| A08 | Academic Context Agent | Current / Future Academic Context Analysis | Official Calendar events through promotion/demand windows. | target month, frozen Calendar artifacts/rules | `academic_context_report.json` | after DATA_QUALITY_GATE | READY |
| A09 | Current Context Validation Agent | Evidence Alignment Validator | Align historical and current context without deleting either evidence type. | A07 + A08 reports | `validation_report.json` | CONTEXT_GATE | READY |
| A10 | Demand Insight Agent | Demand Opportunity Agent | Build Monthly Customer Demand Opportunity: Month → Country → Time → Stage → Direction → School → Demand. | A07 + A08 + A09 reports | `insight_report.json` | INSIGHT_GATE | READY |
| A11 | Critic Agent | Opportunity Critic | Audit Agent 10 claims; no re-analysis. | insight report and cited evidence | `critic_report.json` | CRITIC_GATE | READY |
| A12 | Forecast Agent | Future Demand Opportunity Forecast | Forecast opportunity windows for 7/14/28 days, not orders. | Critic PASS insight + evidence reports | `forecast_report.json` | FORECAST_GATE | READY |
| A13 | Action Agent | Sales & Operations Action Planner | Map forecast to sales, content, product and preparation actions. | forecast report | `action_plan.json`, `action_plan.md` | ACTION_GATE | READY |

## A07 — Historical Demand Analysis contract

`historical_demand_report.json` items must contain: `target_month`, `task_type`, `pattern`, `operational_value`, `country`, `school`, `degree_level`, `monthly_pattern`, `lead_time`, `historical_strength`, `evidence_refs`.

It integrates only frozen/QA-passed historical assets: Historical Demand Inventory, Demand Pattern, Operational Value, WHERE/Market Structure, Historical Lead Time, August Monthly Pattern and school distribution.

## A08 — Academic Context contract

`academic_context_report.json` items must contain: `target_month`, `country`, `school`, `academic_stage`, `event_type`, `event_subtype`, `event_start`, `event_end`, `potential_task_type`, `potential_service_direction`, `promotion_window`, `demand_window`, `context_strength`, `source_url`.

It integrates Calendar collection, standardization, Event Type, Business Taxonomy, Mapping and Promotion Window. It does not assert realized customer demand.

## A09 — Validation contract

Every validation item contains `historical_demand_id`, `calendar_context_id`, `validation_status`, `time_alignment`, `market_alignment`, `evidence_strength`, `reason`, `warnings`.

Allowed `validation_status`: `CURRENTLY_SUPPORTED`, `HISTORICAL_ONLY_VALID`, `CALENDAR_NEW_SIGNAL`, `TEMPORAL_SHIFT`, `CONTEXT_CONFLICT`, `INSUFFICIENT_EVIDENCE`.

## A10 — Monthly Opportunity contract

The country-level record has `target_month`, `country`, `best_operating_window`, `window_start`, `window_end`, `time_evidence_source`, `academic_stages`, `business_directions`, `key_schools`, `school_opportunities`, `historical_evidence`, `calendar_evidence`, `opportunity_strength`, `reason`, `source_artifacts`.

`business_directions` is country-level only. `school_opportunities` alone may carry `specific_task_types` and `service_directions`.

## A11–A13 contracts

- A11 decisions are only `PASS`, `PASS_WITH_WARNINGS`, `RETURN_FOR_REVISION`. A return must include `return_to_agent`, `issue`, `required_fix`.
- A12 output contains `forecast_horizon`, `country`, `best_window`, `academic_stage`, `business_direction`, `key_schools`, `specific_demands`, `opportunity_strength`, `confidence`, `reason`; horizons are `7d`, `14d`, `28d`.
- A13 output contains `time_window`, `country`, `business_direction`, `key_schools`, `specific_demands`, `sales_action`, `content_action`, `product_action`, `preparation_action`, `priority`, `evidence_summary`.
