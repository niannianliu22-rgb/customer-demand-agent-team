# Customer Demand Agent Team

## What It Does

Customer Demand Agent Team is a governed, run-isolated analysis workflow. It combines historical demand, an Academic Calendar, and current context through 13 Agents:

data intake → standardization → quality checks → historical demand analysis → Academic Context → Current Validation → Demand Opportunity → Critic → Forecast → Action.

Every run is controlled by A01 Supervisor, uses the registered A03–A13 workflow, and records artifacts, gates, warnings, model-call audit data, and lineage under one `RUN_ID`.

## Architecture

`A01 Supervisor` dispatches and resumes the workflow. `A02 Knowledge` records governed state. `A03–A06` prepare and validate data; `A07` and `A08` run in parallel; `A09–A13` validate, synthesize, critique, forecast, and produce actions. Nine registered Gates control handoffs. Agents never bypass A01 or a Gate.

## 13-Agent Workflow

`A01 → A02 → A03 → A04 → A05 → A06 → (A07 || A08) → A09 → A10 → A11 → A12 → A13`

## Requirements

- Python 3.10 or later
- Python packages: PyYAML and openpyxl
- Codex CLI, authenticated with `codex login`
- Claude CLI, authenticated with its normal CLI login/session flow

Node.js is not required by the Runtime. ClauDepot is optional and is not a Runtime dependency.

## Installation

```sh
git clone <repository-url>
cd customer-demand-agent-team
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Provider Setup

```sh
codex --help
claude --help
```

This project uses authenticated CLI sessions. It does not require an OpenAI API key or an Anthropic API key. Usually no environment variables are required; `CDAT_RUNTIME_BINDING_CONFIG` is an optional development override only.

## Demo Input

`examples/input/` contains six synthetic Excel workbooks with the same department/year file layout and column schemas as the Runtime expects. They contain no real customer, order, school/course, note, feedback, or revenue data. See [examples/input/README.md](examples/input/README.md).

## Quick Start

Run the governed workflow through the delivery wrapper; it invokes A01 Supervisor only, which creates a new `RUN_ID` and dispatches A03–A13.

```sh
python3 scripts/run_customer_demand_analysis.py \
  --target-month 2026-09 \
  --source-input-dir examples/input
```

For a no-model initialization smoke test, add `--initialize-only`.

## Run Customer Demand Analysis

The wrapper validates six `.xlsx` inputs, initializes a new run through the formal Supervisor CLI, captures its `RUN_ID`, then invokes the formal `--execute <RUN_ID>` path. It prints `RUN_ID`, `RUN_STATUS`, `FORECAST_SUMMARY`, `ACTION_SUMMARY`, and `CLAUDE_VIEW_URL`.

Use `python3 scripts/orchestration/run_agent_team_v2.py --status <RUN_ID>` to inspect a run and the formal Supervisor resume options when a Gate blocks or a run enters human review.

## Output Structure

Each run is isolated:

```text
runs/<RUN_ID>/
  artifacts/   # structured Agent outputs
  gates/       # nine Gate decisions
  audit/       # run-local model and lineage audit data
  quality/     # data-quality outputs
  view/        # read-only view JSON
```

Run outputs may contain confidential input-derived data and are intentionally ignored by Git.

## Claude View

Serve the repository rather than opening HTML directly:

```sh
python3 -m http.server 8080 --directory .
```

Open `http://localhost:8080/claude-view/` for the sanitized demo. To view a locally generated run, open `http://localhost:8080/claude-view/?run_id=<RUN_ID>`. The view is read-only.

## Troubleshooting

- **`codex` or `claude` not found:** install the respective CLI and ensure it is on `PATH`.
- **CLI not logged in:** run `codex login` or complete Claude CLI authentication, then retry.
- **Input directory error:** provide exactly six readable `.xlsx` files; start with `examples/input/`.
- **Model unavailable:** verify CLI login, account access, and the concrete models in `config/models/model_runtime_binding_v1.yaml`.
- **Gate blocked:** inspect `runs/<RUN_ID>/gates/` and `state/runtime_state.json`; do not call downstream Agents directly.
- **Resume:** use the formal Supervisor resume command documented by `run_agent_team_v2.py --help` with the affected `RUN_ID`.
- **Python version:** use Python 3.10 or later and reinstall `requirements.txt` in a fresh virtual environment.

## Project Structure

```text
agents/                 A01–A13 role contracts
config/                 agent, orchestration, model, dimension, and insight configuration
gates/                  Gate specifications
policies/               frozen business and evidence policies
schemas/                structured artifact schemas
scripts/orchestration/  formal A01 Supervisor Runtime and adapters
scripts/data/           deterministic Agent implementations and pipelines
scripts/tests/          delivery smoke tests
examples/               synthetic input and sanitized read-only demo view
claude-view/            static read-only viewer
```
