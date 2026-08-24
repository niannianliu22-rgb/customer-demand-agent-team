# 13 Agent Architecture V2 — Current Capability Alignment

## Purpose and scope

V2 retains the original 13 Agent names and count. It aligns their contracts to the implemented Historical Demand, Academic Calendar, Time Pattern, Monthly Opportunity and Customer Demand Opportunity Contract capabilities. It does not alter frozen data, frozen rules, or prior run artifacts.

## End-to-end structure

```text
Supervisor + Knowledge (cross-cutting)
  Data Intake → Schema Mapping → Data Standardization → Data Quality → DATA_QUALITY_GATE
  Historical Demand Pattern ─┐
  Academic Context ──────────┴→ Current Context Validation → Demand Insight → Critic
                                                                                 ↓
                                                           Forecast → Action
```

Agents 7 and 8 may execute in parallel only after `DATA_QUALITY_GATE` passes. Historical evidence and Calendar context remain separate inputs until Agent 9; Calendar absence never deletes historical demand.

## Design principles

- The 13 names are fixed. `display_role` and `expanded_responsibility` clarify V2 scope only.
- Artifacts are structured and carry `run_id`, version, checksum references and frozen-rule provenance.
- Country conclusions stay at business-direction level. Specific task types and service directions exist only at the school-opportunity level.
- Calendar signals are potential opportunities, not realized orders. Historical counts and Calendar signal counts are never compared as like-for-like quantities.
- Forecast is an opportunity-window forecast, never an order-count or revenue forecast without a separately approved model.

## Current implementation position

The project now has executable V2 contracts for A03–A13 and a Supervisor/Knowledge runtime with structured gates, dependency routing, warning propagation, Human Review pause/resume and stale-artifact invalidation. The runtime has been dry-run verified; no formal end-to-end business run is claimed by this architecture document.
