"""Framework for publishing a governed historical data product.

This module deliberately performs no publication when imported or invoked
without --dry-run. It defines the release contract and validates that a future
publisher may only write an approved versioned package after the required
governance states have been supplied by the orchestrator.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STABLE = "STABLE"
CONDITIONAL = "CONDITIONAL"
BLOCKED_GATE_STATUSES = {"REJECT", "HUMAN_REVIEW_REQUIRED"}
REQUIRED_TRACEABILITY_FIELDS = {
    "source_id", "source_file", "source_sheet", "source_row_id", "year", "department"
}


@dataclass(frozen=True)
class ReleaseRequest:
    run_id: str
    dataset_name: str
    dataset_version: str
    data_gate_status: str
    data_intake_status: str
    schema_mapping_status: str
    schema_gate_status: str
    standardization_status: str
    quality_status: str


def resolve_release_status(request: ReleaseRequest) -> tuple[str, Path]:
    """Validate governance preconditions and choose the only permitted target."""
    if request.data_gate_status in BLOCKED_GATE_STATUSES:
        raise ValueError("Data Gate is not publishable; no processed product may be created")
    if request.data_gate_status not in {"PASS", "CONDITIONAL"}:
        raise ValueError("data_gate_status must be PASS, CONDITIONAL, REJECT, or HUMAN_REVIEW_REQUIRED")
    if any(status != "COMPLETED" for status in (
        request.data_intake_status, request.schema_mapping_status,
        request.standardization_status, request.quality_status,
    )):
        raise ValueError("all producing Agents must be COMPLETED before any publication")
    if request.schema_gate_status != "PASS":
        raise ValueError("stable and candidate products require Schema Gate PASS")
    if request.data_gate_status == "PASS":
        return STABLE, ROOT / "data" / "processed"
    return CONDITIONAL, ROOT / "data" / "processed" / "candidate"


def package_paths(request: ReleaseRequest, release_dir: Path) -> dict[str, Path]:
    """Return paths only; callers must reject any existing target before writing."""
    suffix = request.dataset_version
    base = f"{request.dataset_name}_{suffix}"
    return {
        "xlsx": release_dir / f"{base}.xlsx",
        "csv": release_dir / f"{base}.csv",
        "metadata": release_dir / f"{base}.metadata.json",
        "dictionary": release_dir / f"data_dictionary_{suffix}.md",
        "cleaning_log": release_dir / f"cleaning_log_{suffix}.json",
        "quality_report": release_dir / f"quality_report_{suffix}.json",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a future data-product release; no files are published.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--data-gate-status", required=True)
    parser.add_argument("--dry-run", action="store_true", help="required acknowledgement; this framework never publishes")
    args = parser.parse_args()
    if not args.dry_run:
        parser.error("publication is intentionally disabled in this framework; use --dry-run")
    request = ReleaseRequest(
        run_id=args.run_id, dataset_name="customer_demand_history_2023_2025", dataset_version="v1",
        data_gate_status=args.data_gate_status, data_intake_status="COMPLETED",
        schema_mapping_status="COMPLETED", schema_gate_status="PASS",
        standardization_status="COMPLETED", quality_status="COMPLETED",
    )
    release_status, target = resolve_release_status(request)
    print({"release_status": release_status, "release_path": str(target), "package": {k: str(v) for k, v in package_paths(request, target).items()}})


if __name__ == "__main__":
    main()
