from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _build_signature_from_profile_payload(profile_payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    sheets_payload = profile_payload.get("sheets", []) if isinstance(profile_payload, dict) else []
    sheets: list[dict[str, Any]] = []

    for sheet in sheets_payload:
        if not isinstance(sheet, dict):
            continue

        columns = [_normalize_text(column) for column in sheet.get("columns", []) if column is not None]

        inferred_types_raw = sheet.get("inferred_types", {})
        if not isinstance(inferred_types_raw, dict):
            inferred_types_raw = {}
        inferred_types = {
            _normalize_text(key): _normalize_text(value)
            for key, value in sorted(inferred_types_raw.items(), key=lambda item: _normalize_text(item[0]))
        }

        hints = sorted(_normalize_text(hint) for hint in sheet.get("classifier_hints", []) if hint is not None)

        sheets.append(
            {
                "sheet_name": _normalize_text(sheet.get("name")),
                "visible": bool(sheet.get("visible", True)),
                "header_row": sheet.get("header_row"),
                "columns": columns,
                "inferred_types": inferred_types,
                "likely_business_meaning": _normalize_text(sheet.get("likely_business_meaning")),
                "classifier_hints": hints,
            }
        )

    payload = {"sheet_count": len(sheets), "sheets": sheets}
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return digest, payload


def _discover_pipeline_dirs(artifacts_root: Path) -> list[Path]:
    discovery_roots = [
        artifacts_root / "function_runs",
        artifacts_root / "live_pipeline",
        artifacts_root / "local_pipeline",
        artifacts_root / "local_real_run",
        artifacts_root / "streamlit_runs",
    ]

    run_dirs: list[Path] = []
    seen: set[Path] = set()

    for root in discovery_roots:
        if not root.exists() or not root.is_dir():
            continue

        if root.name == "function_runs":
            for blob_run_dir in root.iterdir():
                if not blob_run_dir.is_dir():
                    continue
                for pipeline_dir in blob_run_dir.glob("pipeline_*"):
                    if pipeline_dir.is_dir() and pipeline_dir not in seen:
                        run_dirs.append(pipeline_dir)
                        seen.add(pipeline_dir)
        else:
            for pipeline_dir in root.glob("pipeline_*"):
                if pipeline_dir.is_dir() and pipeline_dir not in seen:
                    run_dirs.append(pipeline_dir)
                    seen.add(pipeline_dir)

    run_dirs.sort(key=lambda item: item.stat().st_mtime)
    return run_dirs


def _load_cache_entries(cache_entries_dir: Path) -> dict[str, dict[str, Any]]:
    cache_by_fingerprint: dict[str, dict[str, Any]] = {}
    if not cache_entries_dir.exists() or not cache_entries_dir.is_dir():
        return cache_by_fingerprint

    for entry_file in cache_entries_dir.glob("*.json"):
        try:
            payload = json.loads(entry_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        fingerprint = str(payload.get("schema_fingerprint_sha256", "")).strip()
        if fingerprint:
            cache_by_fingerprint[fingerprint] = payload

    return cache_by_fingerprint


def _backfill_run(
    run_dir: Path,
    schema_cache_root: Path,
    schema_cache_entries_dir: Path,
    cache_by_fingerprint: dict[str, dict[str, Any]],
    write_fallback_for_missing_inputs: bool,
) -> tuple[str, str | None]:
    lookup_path = run_dir / "schema_cache_lookup.json"
    fingerprint_path = run_dir / "schema_fingerprint.json"
    profile_path = run_dir / "workbook_profile.json"

    fingerprint = ""
    signature_payload: dict[str, Any] | None = None

    if fingerprint_path.exists():
        try:
            fingerprint_payload = json.loads(fingerprint_path.read_text(encoding="utf-8"))
            fingerprint = str(fingerprint_payload.get("schema_fingerprint_sha256", "")).strip()
            signature_payload = fingerprint_payload.get("schema_signature_payload")
        except Exception:
            fingerprint = ""

    if not fingerprint and profile_path.exists():
        try:
            profile_payload = json.loads(profile_path.read_text(encoding="utf-8"))
        except Exception:
            profile_payload = {}
        fingerprint, signature_payload = _build_signature_from_profile_payload(profile_payload)
        fingerprint_payload = {
            "schema_fingerprint_sha256": fingerprint,
            "schema_signature_payload": signature_payload,
            "backfilled": True,
        }
        fingerprint_path.write_text(json.dumps(fingerprint_payload, indent=2), encoding="utf-8")

    if not fingerprint:
        if not write_fallback_for_missing_inputs:
            return "skipped_missing_inputs", None

        fallback_payload = {
            "schema_fingerprint_sha256": "",
            "lookup_status": "not_found",
            "match_found": False,
            "cache_hit_approved": False,
            "matched_entry_path": "",
            "matched_entry_approval_status": None,
            "planning_source": "planner",
            "cache_root": str(schema_cache_root.resolve()),
            "backfilled": True,
            "lookup_reason": "missing_workbook_profile_and_fingerprint",
            "has_schema_fingerprint_file": fingerprint_path.exists(),
            "has_workbook_profile_file": profile_path.exists(),
        }
        lookup_path.write_text(json.dumps(fallback_payload, indent=2), encoding="utf-8")
        return "fallback_not_found", None

    matched_entry = cache_by_fingerprint.get(fingerprint)
    match_found = matched_entry is not None
    approval_status = matched_entry.get("approval_status") if matched_entry else None
    cache_hit_approved = bool(match_found and approval_status == "approved")

    if cache_hit_approved:
        lookup_status = "known_input_schema"
        planning_source = "schema_cache"
    elif match_found:
        lookup_status = "known_input_schema_unapproved"
        planning_source = "planner"
    else:
        lookup_status = "not_found"
        planning_source = "planner"

    matched_entry_path = ""
    if match_found:
        matched_entry_path = str((schema_cache_entries_dir / f"{fingerprint}.json").resolve())

    lookup_payload = {
        "schema_fingerprint_sha256": fingerprint,
        "lookup_status": lookup_status,
        "match_found": match_found,
        "cache_hit_approved": cache_hit_approved,
        "matched_entry_path": matched_entry_path,
        "matched_entry_approval_status": approval_status,
        "planning_source": planning_source,
        "cache_root": str(schema_cache_root.resolve()),
        "backfilled": True,
    }
    lookup_path.write_text(json.dumps(lookup_payload, indent=2), encoding="utf-8")
    return "backfilled", lookup_status


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill schema cache lookup artifacts for historical pipeline runs.")
    parser.add_argument(
        "--artifacts-root",
        default="artifacts",
        help="Artifacts root directory containing run folders and schema cache.",
    )
    parser.add_argument(
        "--skip-fallback",
        action="store_true",
        help="Skip writing lookup files for runs that lack both fingerprint and workbook profile inputs.",
    )
    args = parser.parse_args()

    artifacts_root = Path(args.artifacts_root).resolve()
    schema_cache_root = artifacts_root / "schema_cache"
    schema_cache_entries_dir = schema_cache_root / "entries"

    run_dirs = _discover_pipeline_dirs(artifacts_root)
    cache_by_fingerprint = _load_cache_entries(schema_cache_entries_dir)

    counters = {
        "backfilled": 0,
        "fallback_not_found": 0,
        "skipped_missing_inputs": 0,
    }
    status_counts = {
        "known_input_schema": 0,
        "known_input_schema_unapproved": 0,
        "not_found": 0,
    }
    failures: list[dict[str, str]] = []

    for run_dir in run_dirs:
        try:
            action, lookup_status = _backfill_run(
                run_dir=run_dir,
                schema_cache_root=schema_cache_root,
                schema_cache_entries_dir=schema_cache_entries_dir,
                cache_by_fingerprint=cache_by_fingerprint,
                write_fallback_for_missing_inputs=not args.skip_fallback,
            )
            counters[action] = counters.get(action, 0) + 1
            if lookup_status:
                status_counts[lookup_status] = status_counts.get(lookup_status, 0) + 1
        except Exception as exc:
            failures.append({"run_dir": str(run_dir), "error": str(exc)})

    summary = {
        "artifacts_root": str(artifacts_root),
        "run_dirs_total": len(run_dirs),
        "actions": counters,
        "lookup_status_counts": status_counts,
        "failures": len(failures),
        "failure_samples": failures[:10],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()