# GATE_MODEL V2

Gates are deterministic verification modules, not Agents. Each gate records required artifacts, result, failed conditions, return target and checksum evidence.

| Gate | Required artifact | Pass condition | Fail condition | Return target |
|---|---|---|---|---|
| SOURCE_GATE | source manifest, source profiles | every expected source registered; readable source profiled or explicitly marked | unregistered/missing accounting | A03 Data Intake Agent |
| SCHEMA_GATE | manifest, profiles, schema mapping | required fields mapped or explicitly governed | required field unaccounted for | A04 Schema Mapping Agent; A03 if profile missing |
| STANDARDIZATION_GATE | unified dataset, cleaning log, standardization rules | lineage, canonical schema and frozen rules verified; no unresolved required conversion | unresolved required standardization values | A05 Data Standardization Agent / human review |
| DATA_QUALITY_GATE | quality report, dataset, cleaning log | required quality metrics and thresholds/evidence present | missing metric or material unresolved quality defect | A06 Data Quality Agent or A05 by defect origin |
| CONTEXT_GATE | historical demand report, academic context report | required reports are traceable, target-month scoped and distinct evidence types | untraceable/mixed evidence or missing report | A07 or A08 |
| INSIGHT_GATE | validation report, insight report | country direction / school demand hierarchy and evidence fields valid | Calendar deletes history; untraceable opportunity; invalid hierarchy | A09 or A10 by defect origin |
| CRITIC_GATE | critic report, insight report, cited evidence | critic decision is valid and all claims reviewed | absent review or unsupported PASS | A11 Critic Agent; `RETURN_FOR_REVISION` routes to named Agent |
| FORECAST_GATE | forecast report, critic PASS | only opportunity-window forecast; every horizon traceable | order/revenue forecast without model; no cited evidence | A12 Forecast Agent |
| ACTION_GATE | action plan, forecast report | each action maps to a forecast item and required action fields | re-judged demand or missing forecast link | A13 Action Agent / A12 if forecast scope missing |

Gate result values are `PASS`, `CONDITIONAL`, `REJECT`, `HUMAN_REVIEW_REQUIRED`. Critic uses its separate V2 decision enumeration in `AGENT_MAP_V2.md`.
