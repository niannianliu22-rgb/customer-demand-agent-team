# AGENT_CONTRACTS V2

## Common envelope

Every machine-readable Agent artifact contains: `run_id`, `agent_id`, `agent_name`, `display_role`, `version`, `status`, `generated_at`, `target_month`, `input_artifacts`, `frozen_rules`, `items`, `unresolved`, `checksum`.

`input_artifacts` entries contain `artifact_path`, `checksum`, `version`, `run_id`. `frozen_rules` entries contain `rule_name`, `version`, `frozen_at`, `artifact_path`, `checksum`, `supersedes`.

## A01–A06 alignment

| Agent | Required input schema | Required output schema | Gate | Failure / return condition |
|---|---|---|---|---|
| A01 Supervisor | agent registry, workflow state, gate result | state event: agent, from_status, to_status, dependency, reason | all gates | unknown return target or unresolved gate → `HUMAN_REVIEW_REQUIRED` |
| A02 Knowledge | artifact and state metadata | append-only ledger entry: agent, rule_name, version, status, frozen_at, artifact_path, checksum, dependency, supersedes | none | unreadable metadata → `INSUFFICIENT_EVIDENCE` entry |
| A03 Data Intake | expected source list, input path | source manifest plus profiles | SOURCE_GATE | inaccessible input root → `FAILED` |
| A04 Schema Mapping | manifest, profiles, canonical/frozen rules | mapping items with source field, canonical field, mapping status, evidence | SCHEMA_GATE | unmapped required field → return A04; missing source profile → return A03 |
| A05 Data Standardization | mapping, input sources, frozen standardization rules | unified dataset, cleaning log, review log, checksums | STANDARDIZATION_GATE | unresolved required values → `HUMAN_REVIEW_REQUIRED`; return A05 after human resolution |
| A06 Data Quality | standardized dataset, cleaning log, canonical schema, frozen rules | `quality_report.json`: metrics, warnings, conclusion, evidence | DATA_QUALITY_GATE | missing required quality metric → return A06; source/standardization defect → return A05 |

## A07–A13 required input/output boundaries

| Agent | Required inputs | Required artifact | Gate / return target |
|---|---|---|---|
| A07 | Data Quality Gate PASS dataset, target month, frozen historical rules | `historical_demand_report.json` | CONTEXT_GATE; upstream data defect → A05/A06 |
| A08 | target month, Calendar standardized/mapping/promotion artifacts and frozen rules | `academic_context_report.json` | CONTEXT_GATE; missing Calendar evidence → unresolved, not fabricated |
| A09 | A07, A08 | `validation_report.json` | INSIGHT_GATE; alignment defect → A07 or A08 |
| A10 | A07, A08, A09 | `insight_report.json` | CRITIC_GATE; critic return → A10 |
| A11 | A10 and all cited evidence | `critic_report.json` | CRITIC_GATE; structural evidence defect → A10 |
| A12 | Critic PASS insight, A07/A08/A09 evidence | `forecast_report.json` | FORECAST_GATE; unsupported horizon → A12 unresolved |
| A13 | A12 forecast | `action_plan.json`, `action_plan.md` | ACTION_GATE; absent forecast scope → A12 |

## Prohibited cross-layer fields

The Monthly Opportunity main output must not default to channel, customer group, degree, DDL, or amount segmentation. These are optional specialist analyses only. Country conclusions must not contain individual `essay`, `assignment`, `project`, or other task types; those belong to a `school_opportunities` item.
