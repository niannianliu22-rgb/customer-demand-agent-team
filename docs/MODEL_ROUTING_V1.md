# Model Routing V1

Model Routing V1 is a frozen, provider-agnostic execution policy. It leaves Agent Contracts, Gate logic, Frozen Business Rules and business calculations unchanged.

The runtime follows `RULE FIRST → CODE FIRST → LLM ONLY WHEN REQUIRED → HUMAN REVIEW WHEN UNCERTAIN`. Gates, checksums, state transitions, schema checks, and all deterministic calculations remain code-only.

`config/models/model_registry_v1.yaml` defines capability tiers rather than vendor bindings. `config/models/model_routing_v1.yaml` binds each Agent to an execution mode, logical primary/fallback model capability, reasoning level, structured envelope, and explicit artifact boundary.

Critical opportunity synthesis (A10) and independent critic audit (A11) require TIER_3 models. Their primary profiles differ, and their fallback must also be TIER_3; when no qualified model is available, the Agent is blocked rather than silently downgraded.

A02 writes prompt-free model-call audit events to `runs/<RUN_ID>/model_call_audit.jsonl`. Each event records only execution metadata, checksums and optional usage/cost figures; prompts and raw sensitive content are forbidden. Dry runs make zero model calls.

## CLI Multi-Provider Runtime

`config/models/model_runtime_binding_v1.yaml` binds logical aliases to local CLI providers, not API keys. Claude uses `claude --print --output-format json --json-schema …`; Codex uses `codex exec --ephemeral --sandbox read-only --output-schema …`. Codex bindings use `DEFAULT_LOGIN_MODEL`, so the CLI selects the model supported by the signed-in ChatGPT account instead of receiving an incompatible API-model ID. Both commands run non-interactively and use their own previously established CLI login sessions.

Preflight checks only the executable and login status (`claude auth status` / `codex login status`); it never makes a billable model request. The primary binding is selected when available. Otherwise, only the configured same-tier fallback may be selected; if neither has a valid CLI login, the Agent is blocked. A10 and A11 have different primary providers to preserve the independent critic path.

The shared `invoke()` entry point in `scripts/orchestration/model_runtime_adapter_v1.py` requires the registered output schema and returns safe audit metadata. It intentionally excludes prompts and raw responses from the audit ledger.

The shared envelope is strict-schema compatible: nested `contract_payload` is limited to a summary, findings, recommendations and optional return target. This is required by Codex structured output and keeps model output advisory; detailed business artifacts remain produced and validated by registered code.
