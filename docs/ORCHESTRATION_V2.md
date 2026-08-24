# ORCHESTRATION V2

## Main flow

1. A01 Supervisor initializes state; A02 Knowledge begins the ledger.
2. A03 Data Intake → SOURCE_GATE → A04 Schema Mapping → SCHEMA_GATE.
3. A05 Data Standardization → STANDARDIZATION_GATE → A06 Data Quality → DATA_QUALITY_GATE.
4. After Data Quality Gate PASS/allowed CONDITIONAL, A07 Historical Demand Analysis and A08 Academic Context Analysis run in parallel.
5. A09 aligns the two independent evidence streams → CONTEXT_GATE.
6. A10 creates the monthly opportunity contract → INSIGHT_GATE.
7. A11 reviews A10 → CRITIC_GATE. `RETURN_FOR_REVISION` routes to `return_to_agent`, ordinarily A10; the Supervisor records the reason and re-runs only the required downstream chain.
8. Only Critic PASS or PASS_WITH_WARNINGS plus CRITIC_GATE pass unlocks A12 Forecast → FORECAST_GATE → A13 Action → ACTION_GATE.

## V2 return rules

- Calendar absence never returns or deletes an A07 historical item; A09 emits `HISTORICAL_ONLY_VALID`.
- Calendar-only evidence may remain and A09 emits `CALENDAR_NEW_SIGNAL`.
- A11 cannot alter data or re-run analysis. It returns a precise contract issue only.
- A05 currently has a recorded `HUMAN_REVIEW_REQUIRED` state in the existing run log. A new end-to-end V2 run must not bypass this via downstream artifacts; it requires a resolved A05 output and A06/Data Quality Gate evidence.

## Knowledge requirements

For every artifact and frozen rule A02 records exactly: `agent`, `rule_name`, `version`, `status`, `frozen_at`, `artifact_path`, `checksum`, `dependency`, `supersedes`. This lets a new session or month reuse frozen rules rather than recreate them.
