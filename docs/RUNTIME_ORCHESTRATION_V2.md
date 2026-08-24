# Runtime Orchestration V2

`A01 Supervisor` owns state transitions and dependency routing. `A02 Knowledge` writes the frozen registry, run manifest and JSONL state-event ledger; it does not make business decisions.

## Commands

```sh
python3 scripts/orchestration/run_agent_team_v2.py --target-month 2026-08 --dry-run
python3 scripts/orchestration/run_agent_team_v2.py --target-month 2026-08
python3 scripts/orchestration/run_agent_team_v2.py --resume RUN_ID
python3 scripts/orchestration/run_status_v2.py RUN_ID
```

The normal new-run command creates an isolated manifest and ledger only. It deliberately does not silently invoke a business Agent: a production Agent adapter must be registered with its run-scoped inputs. This prevents accidental historical analysis, Calendar collection, Forecast, or Action execution.

## Runtime behavior

- A03 → A06 are controlled by their four data gates.
- A07/A08 dispatch as one parallel wave after `DATA_QUALITY_GATE`.
- `HUMAN_REVIEW_REQUIRED` changes the run to `WAITING_FOR_HUMAN`; Resume continues at the current agent without resetting A03.
- `A11 RETURN_FOR_REVISION → A10` invalidates only A10–A13 artifacts. The graph computes this automatically.
- Artifact checksum changes mark the producer and all downstream artifacts `STALE`; stale Forecast/Action outputs cannot be reused.
- `PASS_WITH_WARNINGS` flows through all downstream agents. Critic warnings are Forecast and Action constraints.

`--dry-run` simulates PASS, Standardization failure, precise Critic return, Human Review pause/resume, stale invalidation, and warning propagation without calling business Agents or modifying their artifacts.
