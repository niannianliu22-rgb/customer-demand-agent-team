"""
build_source_manifest.py — Data Intake Agent's manifest-assembly driver.

This is the orchestration glue that a Data Intake Agent run performs around
the deterministic scanner (inspect_excel.py): register expected sources,
match them against what actually exists in runs/{run_id}/input/, assign
source_id, call inspect_excel.py per readable file, and write:
  runs/{run_id}/artifacts/source_manifest.json
  runs/{run_id}/artifacts/source_profiles/source_{NNN}.json

It performs NO business-semantic field mapping — only structural registration,
per the Data Intake Agent contract (agents/data_intake.md).
"""

import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inspect_excel import inspect_excel  # noqa: E402

DEPARTMENTS = ["学管部", "顾问部"]
YEARS = [2023, 2024, 2025]


def parse_year(filename: str):
    m = re.search(r"(20\d{2})", filename)
    return int(m.group(1)) if m else None


def parse_department(filename: str):
    for dept in DEPARTMENTS:
        if dept in filename:
            return dept
    return None


def build(run_id: str):
    root = Path(__file__).resolve().parents[2]
    input_dir = root / "runs" / run_id / "input"
    artifacts_dir = root / "runs" / run_id / "artifacts"
    profiles_dir = artifacts_dir / "source_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    actual_files = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in (".xlsx", ".xls") and not p.name.startswith(".")
    )

    # Match actual files to expected (year, department) grid.
    expected_grid = [(y, d) for y in YEARS for d in DEPARTMENTS]
    matched = {}  # (year, dept) -> Path
    unmatched_files = []

    for f in actual_files:
        y = parse_year(f.name)
        d = parse_department(f.name)
        if y is not None and d is not None and (y, d) in expected_grid:
            if (y, d) in matched:
                unmatched_files.append((f, "duplicate file for same (year, department)"))
            else:
                matched[(y, d)] = f
        else:
            unmatched_files.append((f, f"could not parse (year, department) from filename (year={y}, department={d})"))

    sources = []
    source_seq = 0
    generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def next_source_id():
        nonlocal source_seq
        source_seq += 1
        return f"source_{source_seq:03d}"

    # Registered in a stable order: expected grid first (year, department),
    # so source_id assignment is deterministic and reproducible.
    for (year, dept) in expected_grid:
        source_id = next_source_id()
        f = matched.get((year, dept))
        if f is None:
            sources.append({
                "source_id": source_id,
                "year": year,
                "department": dept,
                "original_file_name": None,
                "file_path": None,
                "sheet_names": [],
                "status": "MISSING",
                "profile_artifact": None,
                "row_count": None,
                "column_count": None,
                "warnings": [],
                "errors": [f"expected source not found in {input_dir.relative_to(root)}"],
            })
            continue

        rel_path = f.relative_to(root)
        profile = inspect_excel(str(f))

        if not profile["readable"]:
            sources.append({
                "source_id": source_id,
                "year": year,
                "department": dept,
                "original_file_name": f.name,
                "file_path": str(rel_path),
                "sheet_names": [],
                "status": "UNREADABLE",
                "profile_artifact": None,
                "row_count": None,
                "column_count": None,
                "warnings": profile["warnings"],
                "errors": profile["errors"],
            })
            continue

        # Write the per-source profile artifact (raw inspect_excel output).
        profile_rel_path = f"runs/{run_id}/artifacts/source_profiles/{source_id}.json"
        profile_out = {
            "run_id": run_id,
            "agent": "Data Intake Agent",
            "source_id": source_id,
            "tool": "scripts/data/inspect_excel.py",
            "generated_at": generated_at,
            **profile,
        }
        (profiles_dir / f"{source_id}.json").write_text(
            json.dumps(profile_out, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        total_rows = sum(s.get("row_count", 0) or 0 for s in profile["sheets"].values())
        total_cols = max((s.get("column_count", 0) or 0 for s in profile["sheets"].values()), default=0)
        all_sheets_empty = all(s.get("is_empty_sheet") for s in profile["sheets"].values())

        status = "PARTIAL" if all_sheets_empty else "RECEIVED"

        sources.append({
            "source_id": source_id,
            "year": year,
            "department": dept,
            "original_file_name": f.name,
            "file_path": str(rel_path),
            "sheet_names": profile["sheet_names"],
            "status": status,
            "profile_artifact": profile_rel_path,
            "row_count": total_rows,
            "column_count": total_cols,
            "warnings": profile["warnings"],
            "errors": profile["errors"],
        })

    # Any real input file that didn't match the expected grid: register it too
    # (no silent omission), flagged UNKNOWN.
    for f, reason in unmatched_files:
        source_id = next_source_id()
        rel_path = f.relative_to(root)
        profile = inspect_excel(str(f))
        profile_rel_path = None
        status = "UNKNOWN"
        row_count = column_count = None
        sheet_names = []
        errs = [reason]
        warns = []
        if profile["readable"]:
            sheet_names = profile["sheet_names"]
            profile_rel_path = f"runs/{run_id}/artifacts/source_profiles/{source_id}.json"
            profile_out = {
                "run_id": run_id,
                "agent": "Data Intake Agent",
                "source_id": source_id,
                "tool": "scripts/data/inspect_excel.py",
                "generated_at": generated_at,
                **profile,
            }
            (profiles_dir / f"{source_id}.json").write_text(
                json.dumps(profile_out, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            row_count = sum(s.get("row_count", 0) or 0 for s in profile["sheets"].values())
            column_count = max((s.get("column_count", 0) or 0 for s in profile["sheets"].values()), default=0)
            warns = profile["warnings"]
        else:
            errs += profile["errors"]

        sources.append({
            "source_id": source_id,
            "year": parse_year(f.name),
            "department": parse_department(f.name),
            "original_file_name": f.name,
            "file_path": str(rel_path),
            "sheet_names": sheet_names,
            "status": status,
            "profile_artifact": profile_rel_path,
            "row_count": row_count,
            "column_count": column_count,
            "warnings": warns,
            "errors": errs,
        })

    manifest = {
        "run_id": run_id,
        "agent": "Data Intake Agent",
        "wave": "W1",
        "version": 1,
        "generated_at": generated_at,
        "status": "COMPLETED",
        "expected_source_count": len(expected_grid),
        "received_source_count": sum(1 for s in sources if s["status"] == "RECEIVED"),
        "sources": sources,
        "evidence_refs": [
            {"type": "tool", "ref": "scripts/data/inspect_excel.py"},
            {"type": "directory_scan", "ref": f"runs/{run_id}/input/"},
        ],
        "unresolved": [
            {"source_id": s["source_id"], "status": s["status"], "reason": (s["errors"] or ["see warnings"])[0]}
            for s in sources if s["status"] in ("MISSING", "UNREADABLE", "UNKNOWN", "PARTIAL")
        ],
        "notes": [
            "expected_source_count assumed = 2 departments x 3 years (2023/2024/2025), "
            "derived from project scope documented in docs/ARCHITECTURE.md; "
            "no separate run-config artifact existed in runs/{run_id}/ to source this from."
        ],
    }

    (artifacts_dir / "source_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return manifest


if __name__ == "__main__":
    run_id = sys.argv[1] if len(sys.argv) > 1 else "RUN-202608-DEMAND-001"
    result = build(run_id)
    print(json.dumps({
        "run_id": result["run_id"],
        "expected_source_count": result["expected_source_count"],
        "received_source_count": result["received_source_count"],
        "sources_summary": [
            {"source_id": s["source_id"], "year": s["year"], "department": s["department"],
             "status": s["status"], "sheet_names": s["sheet_names"],
             "row_count": s["row_count"], "column_count": s["column_count"]}
            for s in result["sources"]
        ],
    }, ensure_ascii=False, indent=2))
