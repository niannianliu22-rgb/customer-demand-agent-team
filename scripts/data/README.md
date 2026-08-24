# Data Script Scope

The delivery Runtime invokes only the entrypoints registered in `config/orchestration/agent_dispatch_registry_v1.yaml`. Those entrypoints receive the current `RUN_ID` from A01 Supervisor and must not use a fixed historical run.

Other scripts in this directory are historical deterministic preparation, confirmation, remediation, and frozen-evidence utilities. Some intentionally retain `RUN-202608-DEMAND-001` references as provenance for the archived rule-building process. They are not Quick Start commands, are not invoked by the delivery wrapper, and must not be used to process a new run directly.
