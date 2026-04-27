#!/usr/bin/env python
"""Backfill notes.json artifact AND per-row 'Notes JSON' column for all pipeline runs.

For each pipeline run directory:
1. Rebuild notes.json artifact from planner_response.json + sandbox notes.
2. Add/overwrite 'Notes JSON' column in canonical_output.csv and canonical_output.xlsx
   by inspecting each row's Origin Note, Destination Note, Bid Note fields.

Usage:
    python scripts/backfill-notes-json.py [--dry-run] [--force]

Flags:
    --dry-run   Print what would be done without writing files.
    --force     Overwrite notes.json even if it already exists.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

try:
    from openpyxl import Workbook
except ImportError:
    Workbook = None  # type: ignore[assignment,misc]

ARTIFACTS_ROOT = Path(__file__).resolve().parent.parent / "artifacts"

DISCOVERY_ROOTS = [
    ARTIFACTS_ROOT / "function_runs",
    ARTIFACTS_ROOT / "live_pipeline",
    ARTIFACTS_ROOT / "local_pipeline",
    ARTIFACTS_ROOT / "local_real_run",
    ARTIFACTS_ROOT / "streamlit_runs",
]

NOTE_COLUMN_FIELDS = ["Origin Note", "Destination Note", "Bid Note"]


# ── Discovery ────────────────────────────────────────────────────

def _discover_pipeline_dirs() -> list[Path]:
    discovered: list[Path] = []
    seen: set[Path] = set()

    for root in DISCOVERY_ROOTS:
        if not root.exists() or not root.is_dir():
            continue

        if root.name == "function_runs":
            for blob_run_dir in root.iterdir():
                if not blob_run_dir.is_dir():
                    continue
                for pipeline_dir in blob_run_dir.glob("pipeline_*"):
                    if pipeline_dir.is_dir() and pipeline_dir not in seen:
                        discovered.append(pipeline_dir)
                        seen.add(pipeline_dir)
        else:
            for pipeline_dir in root.glob("pipeline_*"):
                if pipeline_dir.is_dir() and pipeline_dir not in seen:
                    discovered.append(pipeline_dir)
                    seen.add(pipeline_dir)

    discovered.sort(key=lambda p: p.name)
    return discovered


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ── notes.json artifact helpers ──────────────────────────────────

def _extract_planner_notes(planner: dict[str, Any]) -> list[dict[str, Any]]:
    raw = planner.get("notes_json")
    if not isinstance(raw, list):
        return []
    notes: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            entry = dict(item)
            entry.setdefault("origin", "planner")
            notes.append(entry)
    return notes


def _extract_sandbox_notes(sandbox: dict[str, Any]) -> list[dict[str, Any]]:
    result = sandbox.get("result")
    if not isinstance(result, dict):
        return []
    raw = result.get("notes")
    if not isinstance(raw, list):
        return []
    notes: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            entry = dict(item)
            entry.setdefault("origin", "transform")
            notes.append(entry)
    return notes


def _synthesize_notes_from_planner(planner: dict[str, Any]) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []

    for assumption in planner.get("assumptions", []):
        if isinstance(assumption, str) and assumption.strip():
            notes.append({
                "category": "assumption",
                "note": assumption.strip(),
                "severity": "info",
                "origin": "planner_backfill",
            })

    mapping_plan = planner.get("mapping_plan", {})
    if isinstance(mapping_plan, dict):
        for canonical_field, source_expr in mapping_plan.items():
            if not isinstance(canonical_field, str) or not isinstance(source_expr, str):
                continue
            if "note" in canonical_field.lower():
                notes.append({
                    "category": "mapping",
                    "source_column": source_expr,
                    "note": f"{canonical_field} mapped from: {source_expr}",
                    "severity": "info",
                    "origin": "planner_backfill",
                })

    return notes


def _build_notes_artifact(
    planner_notes: list[dict[str, Any]],
    sandbox_notes: list[dict[str, Any]],
) -> dict[str, Any]:
    combined = planner_notes + sandbox_notes
    return {
        "total_notes": len(combined),
        "planner_note_count": len(planner_notes),
        "transform_note_count": len(sandbox_notes),
        "notes": combined,
    }


# ── Per-row Notes JSON column helpers ────────────────────────────

def _build_row_notes_json(record: dict[str, Any]) -> str:
    """Build the per-row Notes JSON string from note-like fields in a record."""
    notes_array: list[dict[str, str]] = []
    for field in NOTE_COLUMN_FIELDS:
        value = record.get(field, "")
        if value and str(value).strip():
            notes_array.append({"field": field, "value": str(value).strip()})
    return json.dumps(notes_array)


def _backfill_csv(csv_path: Path, dry_run: bool) -> tuple[int, int]:
    """Add/update Notes JSON column in CSV. Returns (total_rows, rows_with_notes)."""
    if not csv_path.exists():
        return 0, 0

    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if not rows:
        return 0, 0

    # Ensure Notes JSON is the last column
    if "Notes JSON" in fieldnames:
        fieldnames.remove("Notes JSON")
    fieldnames.append("Notes JSON")

    rows_with_notes = 0
    for row in rows:
        notes_json_str = _build_row_notes_json(row)
        row["Notes JSON"] = notes_json_str
        if notes_json_str != "[]":
            rows_with_notes += 1

    if not dry_run:
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    return len(rows), rows_with_notes


def _backfill_xlsx(xlsx_path: Path, csv_path: Path, dry_run: bool) -> None:
    """Regenerate XLSX from the updated CSV data."""
    if not xlsx_path.exists() or Workbook is None or dry_run:
        return
    if not csv_path.exists():
        return

    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    wb = Workbook()
    ws = wb.active
    ws.title = "CanonicalOutput"
    ws.append(fieldnames)
    for row in rows:
        ws.append([row.get(col, "") for col in fieldnames])
    wb.save(xlsx_path)


# ── Main ─────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill notes.json and per-row Notes JSON column.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without writing files.")
    parser.add_argument("--force", action="store_true", help="Overwrite notes.json even if it already exists.")
    args = parser.parse_args()

    dirs = _discover_pipeline_dirs()
    print(f"Discovered {len(dirs)} pipeline run(s).\n")

    artifact_written = 0
    artifact_skipped = 0
    csv_updated = 0

    for run_dir in dirs:
        notes_path = run_dir / "notes.json"
        csv_path = run_dir / "canonical_output.csv"
        xlsx_path = run_dir / "canonical_output.xlsx"

        planner = _read_json(run_dir / "planner_response.json")
        sandbox = _read_json(run_dir / "sandbox_execution_report.json")

        # ── 1. notes.json artifact ────────────────────────────────
        if planner is not None:
            if notes_path.exists() and not args.force:
                print(f"  KEEP   {run_dir.name}/notes.json  (use --force to overwrite)")
            else:
                planner_notes = _extract_planner_notes(planner)
                if not planner_notes:
                    planner_notes = _synthesize_notes_from_planner(planner)
                sandbox_notes = _extract_sandbox_notes(sandbox) if sandbox else []
                payload = _build_notes_artifact(planner_notes, sandbox_notes)

                if args.dry_run:
                    print(f"  WOULD  {run_dir.name}/notes.json  ({payload['total_notes']} notes)")
                else:
                    notes_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
                    print(f"  WROTE  {run_dir.name}/notes.json  ({payload['total_notes']} notes)")
                artifact_written += 1

        # ── 2. Per-row Notes JSON in CSV/XLSX ─────────────────────
        if csv_path.exists():
            total_rows, rows_with_notes = _backfill_csv(csv_path, args.dry_run)
            if total_rows > 0:
                if args.dry_run:
                    print(f"  WOULD  {run_dir.name}/canonical_output.csv  ({rows_with_notes}/{total_rows} rows with notes)")
                else:
                    _backfill_xlsx(xlsx_path, csv_path, args.dry_run)
                    print(f"  UPDT   {run_dir.name}/canonical_output.csv+xlsx  ({rows_with_notes}/{total_rows} rows with notes)")
                csv_updated += 1
        else:
            if planner is None:
                print(f"  SKIP   {run_dir.name}  (no planner, no CSV)")
                artifact_skipped += 1

    print(f"\nDone. Artifacts: {artifact_written}, CSVs updated: {csv_updated}, Skipped: {artifact_skipped}")


if __name__ == "__main__":
    main()
