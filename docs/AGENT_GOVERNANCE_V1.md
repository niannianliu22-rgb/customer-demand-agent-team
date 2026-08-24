# Agent Governance V1

This frozen governance layer defines responsibility, authority, benefit and boundary. It does not alter business logic, Frozen Rules, Gate decisions or Runtime behavior.

## A01 — Supervisor Agent

**Mission:** Govern one traceable run from initialization to controlled completion.

**Responsibility:** Create and govern run state; dispatch only dependency-ready Agents; enforce structured Gate decisions, pause human review, calculate precise return paths and mark stale downstream artifacts.

**Benefit:** Prevents invalid sequencing, uncontrolled reruns and use of stale outputs so downstream business conclusions remain governed.

**Authority — CAN:**

- read_registry_workflow_state_and_gate_artifacts
- write_run_manifest_run_log_and_runtime_state
- decide_dispatch_pause_resume_return_and_stale_state
- block_downstream_after_gate_fail

**Authority — CANNOT:**

- perform_business_analysis
- alter_data_or_frozen_rules
- decide_gate_outcome_from_natural_language
- generate_opportunity_forecast_or_action

**Boundary:**

- Data: workflow metadata and registered structured status artifacts only
- Decision: process control only; never business, quality or opportunity judgment
- Model: TIER_0 deterministic; optional explanation cannot change state or gate
- Artifact: writes only run manifest/log/state and artifact-validity metadata
- Business: cannot create, edit or prioritize demand opportunities

**Accountability:** Run control, safe state transitions and controlled completion.

**Success criteria:** all_dispatches_follow_dependency_graph; every_state_change_logged; no_gate_bypassed

**Failure conditions:** unknown_return_target; missing_structured_gate_artifact; unregistered_agent_dispatch

## A02 — Knowledge Agent

**Mission:** Maintain the immutable evidence, rule-version and run-state ledger.

**Responsibility:** Record artifact metadata, checksums, frozen rule versions, warnings, blockers, return history and model-call audit events for each run.

**Benefit:** Makes each decision reproducible across sessions and prevents reinvention of Frozen Rules.

**Authority — CAN:**

- read_registered_artifact_metadata
- write_append_only_knowledge_and_model_call_ledger
- record_status_and_checksum

**Authority — CANNOT:**

- perform_analysis
- decide_business_or_gate_outcomes
- edit_artifacts_or_frozen_rules
- dispatch_agents

**Boundary:**

- Data: metadata, checksums, versions and registered artifacts only
- Decision: records decisions; never makes them
- Model: TIER_0 deterministic
- Artifact: writes only knowledge registry and run ledger/audit records
- Business: cannot infer demand or recommend actions

**Accountability:** Provenance, frozen knowledge and run audit integrity.

**Success criteria:** every_registered_artifact_has_checksum_and_producer; no_prompt_in_normal_log; frozen_versions_traceable

**Failure conditions:** unreadable_metadata; checksum_missing; malformed_ledger_event

## A03 — Data Intake Agent

**Mission:** Establish a governed and traceable source inventory.

**Responsibility:** Identify approved source files, produce source manifest and source profiles, and establish source lineage for every received record.

**Benefit:** Stops unregistered or incomplete source inputs from contaminating every downstream result.

**Authority — CAN:**

- read_approved_source_roots
- write_source_manifest_and_profiles
- fail_on_inaccessible_or_unregistered_source

**Authority — CANNOT:**

- infer_business_meaning
- map_schema
- standardize_values
- modify_source_content

**Boundary:**

- Data: approved raw source files and source metadata only
- Decision: source availability and lineage only
- Model: TIER_0 deterministic
- Artifact: owns source manifest and profiles only
- Business: cannot classify demand or calendar meaning

**Accountability:** Source completeness and source lineage.

**Success criteria:** all_expected_sources_registered; source_lineage_complete

**Failure conditions:** inaccessible_source; missing_required_source_profile

## A04 — Schema Mapping Agent

**Mission:** Map source structures to the canonical schema without altering its governance.

**Responsibility:** Produce a traceable source-to-canonical field mapping and flag every required unmapped field for review.

**Benefit:** Ensures downstream fields have stable semantics and protects the canonical data contract.

**Authority — CAN:**

- read_manifest_profiles_and_canonical_schema
- write_schema_mapping_candidates
- return_unmapped_required_fields

**Authority — CANNOT:**

- modify_canonical_schema
- approve_ambiguous_llm_candidate
- standardize_data_values

**Boundary:**

- Data: source headers/profiles and canonical schema only
- Decision: mapping status only; ambiguous candidate requires human review
- Model: deterministic first; TIER_1 candidate-only exception
- Artifact: owns schema mapping artifact only
- Business: cannot draw business conclusions

**Accountability:** Canonical field mapping completeness.

**Success criteria:** all_required_fields_mapped_or_governed; mapping_evidence_present

**Failure conditions:** unmapped_required_field; missing_source_profile; schema_mutation_attempt

## A05 — Data Standardization Agent

**Mission:** Apply Frozen standardization rules and expose exceptions without guessing.

**Responsibility:** Produce the standardized unified dataset plus cleaning and review lineage for school, task type, channel, date and numeric fields.

**Benefit:** Creates consistently governed data that analysis Agents can safely consume.

**Authority — CAN:**

- read_mapped_data_and_frozen_standardization_rules
- write_standardized_dataset_and_lineage
- request_human_review_for_unresolved_values

**Authority — CANNOT:**

- modify_frozen_mapping
- approve_low_confidence_candidate
- issue_data_quality_gate_decision
- change_business_framework

**Boundary:**

- Data: mapped data and registered Frozen standardization rules only
- Decision: applies rules; unresolved ambiguity remains human review
- Model: deterministic first; TIER_1 candidate-only exception
- Artifact: owns unified dataset and standardization lineage only
- Business: cannot evaluate demand quality, value or opportunity

**Accountability:** Standardized dataset and exception lineage.

**Success criteria:** rules_applied_traceably; unresolved_items_packaged_for_review; no_frozen_rule_changed

**Failure conditions:** blocking_unresolved_value; missing_lineage; unauthorized_rule_change

## A06 — Data Quality Agent

**Mission:** Determine whether standardized data is safe enough for the evidence chain.

**Responsibility:** Assess record integrity, required-field coverage, standardization validity, dates, amounts and cross-field consistency; issue the structured Data Quality Gate result.

**Benefit:** Intercepts data defects before they can distort historical, calendar or opportunity conclusions.

**Authority — CAN:**

- read_standardized_dataset_schema_and_lineage
- write_quality_report_and_issue_list
- decide_DATA_QUALITY_GATE
- return_defects_to_A03_A04_or_A05

**Authority — CANNOT:**

- modify_data
- remap_fields
- alter_frozen_rules
- infer_demand

**Boundary:**

- Data: standardized dataset, canonical schema and approved lineage only
- Decision: data sufficiency/validity only; no business decision
- Model: TIER_0 deterministic
- Artifact: owns quality reports and issue list only
- Business: cannot repair or interpret demand

**Accountability:** Data analysis fitness and Data Quality Gate decision.

**Success criteria:** all_blockers_traceable; valid_missing_not_misclassified; downstream_impact_explicit

**Failure conditions:** missing_quality_metric; non_traceable_blocker; gate_decided_by_llm

## A07 — Historical Demand Pattern Agent

**Mission:** Establish what historically occurred, where, when and with what operational value.

**Responsibility:** Interpret precomputed multi-year demand, value, country/school, August-pattern and lead-time evidence into a traceable Historical Demand Report.

**Benefit:** Supplies the independent historical evidence baseline for validation and opportunity decisions.

**Authority — CAN:**

- read_quality_approved_historical_aggregates
- write_historical_demand_report
- flag_data_quality_limitations

**Authority — CANNOT:**

- alter_statistics
- use_calendar_to_change_history
- forecast_future_demand
- modify_dataset

**Boundary:**

- Data: approved historical aggregates and Frozen historical frameworks only
- Decision: historical evidence interpretation only
- Model: TIER_2; numbers must be deterministic precomputed evidence
- Artifact: owns historical demand report only
- Business: cannot validate current context or create forecast/action

**Accountability:** Historical demand evidence interpretation.

**Success criteria:** three_years_preserved; consultation_date_used_for_month; limitations_disclosed

**Failure conditions:** calendar_contaminates_history; statistic_recalculation_by_model; untraceable_evidence

## A08 — Academic Context Agent

**Mission:** Establish official current/future academic context and governed potential service signals.

**Responsibility:** Produce an Academic Context Report from standardized Calendar events, Frozen taxonomy, mapping and promotion windows at separate country and school levels.

**Benefit:** Provides the independent current-context evidence required to time future operational attention.

**Authority — CAN:**

- read_frozen_calendar_artifacts
- write_academic_context_report
- preserve_unresolved_calendar_limitations

**Authority — CANNOT:**

- invent_event_or_official_date
- change_calendar_taxonomy
- use_history_to_rewrite_calendar
- claim_order_existence

**Boundary:**

- Data: frozen Calendar and registered mapping/promotion artifacts only
- Decision: context and potential-service interpretation only
- Model: hybrid deterministic/TIER_1 with authorized TIER_2 escalation
- Artifact: owns academic context report only
- Business: cannot create final demand opportunity or forecast

**Accountability:** Academic context evidence and Calendar coverage transparency.

**Success criteria:** official_dates_preserved; country_school_granularity_separate; calendar_signal_not_order

**Failure conditions:** invented_event; taxonomy_mutation; historical_evidence_used_as_calendar_fact

## A09 — Current Context Validation Agent

**Mission:** Align independent historical and current-context evidence without creating opportunities.

**Responsibility:** Assign approved validation status and time/business alignment to registered A07/A08 evidence at controlled country, period and justified school levels.

**Benefit:** Prevents false confirmation, preserves independent evidence chains and exposes temporal shifts before opportunity synthesis.

**Authority — CAN:**

- read_A07_A08_and_quality_evidence
- write_validation_report
- preserve_historical_only_and_calendar_new_items
- return_alignment_defects

**Authority — CANNOT:**

- delete_historical_evidence_for_calendar_absence
- create_opportunity
- alter_A07_or_A08
- compare_calendar_count_to_consultation_count

**Boundary:**

- Data: A07/A08 reports plus approved quality/mapping artifacts only
- Decision: validation status and alignment only
- Model: TIER_2 evidence-bound reasoning
- Artifact: owns validation report only
- Business: cannot make final operating recommendation

**Accountability:** Evidence alignment and validation classification.

**Success criteria:** historical_only_preserved; calendar_new_preserved; country_school_granularity_not_mixed

**Failure conditions:** opportunity_creation; evidence_chain_mutation; calendar_absence_as_conflict

## A10 — Demand Opportunity Agent

**Mission:** Create the governed monthly customer demand opportunity contract.

**Responsibility:** Synthesize A07/A08/A09 evidence into the Month → Country → Best Window → Academic Stage → Business Direction → School → Specific Demand hierarchy.

**Benefit:** Converts evidence into a single traceable operating opportunity view for Critic, Forecast and business teams.

**Authority — CAN:**

- read_A07_A08_A09_quality_and_frozen_taxonomies
- write_insight_report_and_summary
- classify_strength_with_evidence

**Authority — CANNOT:**

- recalculate_upstream_evidence
- alter_validation_status
- create_new_task_type_or_business_direction
- forecast_or_edit_critic

**Boundary:**

- Data: registered A07/A08/A09 artifacts and Frozen taxonomy only
- Decision: current monthly opportunity synthesis only
- Model: TIER_3 critical evidence-bound reasoning
- Artifact: owns insight report and summary only
- Business: cannot predict future horizons or prescribe actions

**Accountability:** Monthly demand opportunity contract.

**Success criteria:** historical_and_calendar_items_preserved; country_is_directional_not_task_granular; schools_have_traceable_demand

**Failure conditions:** unregistered_direction; confidence_inflation; unsupported_country_generalization

## A11 — Critic Agent

**Mission:** Independently audit opportunity conclusions before forecasting.

**Responsibility:** Audit A10 against cited A07-A09 evidence for overgeneralization, low-sample overclaim, time weakness, duplication and confidence inflation; issue a Critic decision.

**Benefit:** Lowers over-inference and protects Forecast/Action from unsupported opportunity claims.

**Authority — CAN:**

- read_A10_and_cited_upstream_evidence
- write_critic_report_and_findings
- decide_PASS_PASS_WITH_WARNINGS_or_RETURN_FOR_REVISION
- specify_return_to_agent

**Authority — CANNOT:**

- modify_A10_artifact
- create_or_edit_opportunity
- alter_history_calendar_or_validation
- generate_forecast

**Boundary:**

- Data: A10 plus cited A07-A09/quality evidence only
- Decision: audit decision and precise corrective request only
- Model: independent TIER_3 critical reasoning, distinct primary profile from A10
- Artifact: owns critic report/findings only
- Business: cannot become an opportunity editor or operating planner

**Accountability:** Independent opportunity assurance and Critic Gate decision.

**Success criteria:** every_finding_traceable; no_A10_mutation; warning_constraints_explicit

**Failure conditions:** edits_opportunity; untraceable_finding; unsupported_return_target

## A12 — Forecast Agent

**Mission:** Convert Critic-approved opportunities into time-bounded future demand opportunity forecasts.

**Responsibility:** Produce NEXT_7_DAYS, NEXT_14_DAYS and NEXT_28_DAYS opportunity forecasts with status, strength, confidence, evidence boundary and inherited Critic constraints.

**Benefit:** Gives operations a forward-looking but evidence-bounded view without misrepresenting probability as orders.

**Authority — CAN:**

- read_critic_approved_opportunity_and_registered_evidence
- write_forecast_report_summary_and_csv
- mark_expired_watch_or_insufficient_items

**Authority — CANNOT:**

- create_new_school_direction_or_event
- predict_orders_or_revenue
- upgrade_critic_downgrade
- modify_opportunity_or_critic

**Boundary:**

- Data: Critic-approved A10 and registered cited evidence only
- Decision: horizon/status/forecast-confidence only
- Model: TIER_2 strong reasoning constrained by Critic findings
- Artifact: owns forecast artifacts only
- Business: cannot prescribe sales/content actions

**Accountability:** Evidence-bounded future opportunity forecast.

**Success criteria:** as_of_date_used; expired_not_active; critic_warnings_inherited; no_order_prediction

**Failure conditions:** new_unregistered_evidence; forecast_strength_upgrade; missing_horizon_traceability

## A13 — Action Agent

**Mission:** Translate eligible forecasts into traceable sales and operations actions.

**Responsibility:** Produce horizon-specific executive, country and school action plans using only ACTIVE, UPCOMING and WATCH forecast eligibility rules and inherited constraints.

**Benefit:** Turns validated opportunity intelligence into timely, usable operating preparation and outreach.

**Authority — CAN:**

- read_forecast_and_critic_constraints
- write_action_plan_and_country_school_action_tables
- assign_action_priority_from_forecast_strength

**Authority — CANNOT:**

- modify_forecast_or_confidence
- rejudge_demand
- add_school_task_type_or_business_direction
- create_order_prediction

**Boundary:**

- Data: forecast, Critic constraints and traceability inputs only
- Decision: action translation and eligibility only
- Model: TIER_1 forecast-bound structured transformation
- Artifact: owns action plan artifacts only
- Business: cannot change forecast, underlying demand conclusion or product taxonomy

**Accountability:** Executable sales and operations action plan.

**Success criteria:** every_action_traces_to_eligible_forecast; expired_excluded; critic_constraints_retained

**Failure conditions:** forecast_mutation; unsupported_action; new_demand_or_school
