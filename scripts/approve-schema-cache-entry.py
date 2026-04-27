from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _resolve_artifacts_root(path_text: str) -> Path:
    return Path(path_text).resolve()


def _fingerprint_from_run_dir(run_dir: Path) -> str:
    candidates = [
        run_dir / "schema_fingerprint.json",
        run_dir / "schema_cache_lookup.json",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        fingerprint = str(payload.get("schema_fingerprint_sha256", "")).strip()
        if fingerprint:
            return fingerprint
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Approve a schema cache entry so exact matches can reuse cached planner output.")
    parser.add_argument("--fingerprint", default="", help="Schema fingerprint SHA-256 to approve.")
    parser.add_argument("--run-dir", default="", help="Pipeline run directory containing schema_fingerprint.json or schema_cache_lookup.json.")
    parser.add_argument("--artifacts-root", default="artifacts", help="Artifacts root containing schema_cache/entries.")
    parser.add_argument("--approval-source", default="human", help="Approval source value to store.")
    parser.add_argument("--disable-auto-approve", action="store_true", help="Set auto_approve_enabled=false instead of true.")
    args = parser.parse_args()

    artifacts_root = _resolve_artifacts_root(args.artifacts_root)
    entries_dir = artifacts_root / "schema_cache" / "entries"

    fingerprint = args.fingerprint.strip()
    if not fingerprint and args.run_dir.strip():
        fingerprint = _fingerprint_from_run_dir(Path(args.run_dir).resolve())

    if not fingerprint:
        raise SystemExit("No fingerprint provided. Use --fingerprint or --run-dir.")

    entry_path = entries_dir / f"{fingerprint}.json"
    if not entry_path.exists():
        raise SystemExit(f"Schema cache entry not found: {entry_path}")

    payload = json.loads(entry_path.read_text(encoding="utf-8"))
    payload["approval_status"] = "approved"
    payload["approval_source"] = args.approval_source
    payload["auto_approve_enabled"] = not args.disable_auto_approve
    payload["last_seen_at"] = _utc_now_iso()
    payload.setdefault("metadata", {})
    if isinstance(payload["metadata"], dict):
        payload["metadata"]["approved_at"] = _utc_now_iso()

    entry_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "entry_path": str(entry_path),
                "schema_fingerprint_sha256": fingerprint,
                "approval_status": payload.get("approval_status"),
                "approval_source": payload.get("approval_source"),
                "auto_approve_enabled": payload.get("auto_approve_enabled"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()