# Agent Interaction Map V1

## Delivery and control flow

`A01` controls the flow; `A02` records every state, artifact and warning. Neither performs business analysis.

```text
A03 → SOURCE_GATE → A04 → SCHEMA_GATE → A05 → STANDARDIZATION_GATE → A06 → DATA_QUALITY_GATE
                                                                          ├→ A07 Historical ─┐
                                                                          └→ A08 Academic ───┤
                                                                                              ↓
                                                                                            A09 → CONTEXT_GATE → A10 → INSIGHT_GATE → A11 → CRITIC_GATE → A12 → FORECAST_GATE → A13 → ACTION_GATE
```

## Handoffs, checks and returns

| From | Delivers | To | Gate / check | Return authority | Cannot bypass |
|---|---|---|---|---|---|
| A01 | run_manifest; run_log; runtime_state; final_run_status; stale_state | A02; A03 | Supervisor-controlled handoff | route_to_registered_return_target | A01 / applicable Gate |
| A02 | knowledge_ledger; frozen_registry_snapshot; model_call_audit | A01 | Supervisor-controlled handoff | None | A01 / applicable Gate |
| A03 | source_manifest; source_profiles | A04 | SOURCE_GATE | None | A01 / applicable Gate |
| A04 | schema_mapping | A05 | SCHEMA_GATE | A03_for_missing_profile | A01 / applicable Gate |
| A05 | unified_dataset; cleaning_log; review_log; standardization_lineage | A06 | STANDARDIZATION_GATE | A04_for_schema_defect | A01 / applicable Gate |
| A06 | quality_report; data_quality_issues; data_quality_gate_report | A07; A08 | DATA_QUALITY_GATE | A03; A04; A05 | A01 / applicable Gate |
| A07 | historical_demand_report | A09 | Supervisor-controlled handoff | A05; A06_for_data_defect | A01 / applicable Gate |
| A08 | academic_context_report | A09 | Supervisor-controlled handoff | A05_or_A06_for_data_linkage_defect | A01 / applicable Gate |
| A09 | validation_report | A10 | CONTEXT_GATE | A07; A08 | A01 / applicable Gate |
| A10 | insight_report; demand_opportunity_summary | A11 | INSIGHT_GATE | A09_for_validation_contract_defect | A01 / applicable Gate |
| A11 | critic_report; critic_findings; critic_summary | A12 | CRITIC_GATE | A07; A08; A09; A10 | A01 / applicable Gate |
| A12 | forecast_report; forecast_summary; forecast_opportunities | A13 | FORECAST_GATE | A10_or_A11_for_input_contract_defect | A01 / applicable Gate |

## Required checks and balances

- A01 Supervisor ≠ business decision maker; it only sequences registered decisions.
- A02 Knowledge ≠ analysis Agent; it records evidence and state only.
- A05 Standardization ≠ A06 Data Quality; A05 applies rules, while A06 independently judges fitness.
- A07 Historical ≠ A12 Forecast; historical evidence cannot become a future forecast without A09–A11.
- A08 Academic Context ≠ A10 Opportunity; Calendar signals remain potential context until synthesis.
- A09 Validation ≠ opportunity creator; it classifies alignment only.
- A10 Opportunity ≠ A12 Forecast; monthly synthesis precedes time-horizon forecasting.
- A11 Critic ≠ opportunity editor; it returns a precise correction without changing A10.
- A12 Forecast ≠ A13 Action; forecast confidence is immutable to A13.

## Return and stale rule

Only A01 calculates downstream invalidation from the dependency graph. An Agent may identify its registered return target, but cannot skip an upstream Gate or directly invoke another Agent.
