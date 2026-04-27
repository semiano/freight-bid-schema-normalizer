from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..models.contracts import AgentResponse, SchemaCacheEntry, SchemaFingerprint


def resolve_local_schema_cache_root(output_root: str) -> Path:
    configured_root = os.getenv("SCHEMA_CACHE_ROOT", "").strip()
    if configured_root:
        return Path(configured_root).expanduser().resolve()

    output_path = Path(output_root).resolve()
    for candidate in (output_path, *output_path.parents):
        if candidate.name.strip().lower() == "artifacts":
            return candidate / "schema_cache"

    return output_path.parent / "schema_cache"


def _hash_planner_output(planner_output: dict[str, Any]) -> str:
    canonical_json = json.dumps(planner_output, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class LocalSchemaCacheRepository:
    def __init__(self, root_dir: str) -> None:
        self.root_dir = Path(root_dir)
        self.entries_dir = self.root_dir / "entries"
        self.history_dir = self.root_dir / "history"
        self.entries_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _entry_path(self, fingerprint: str) -> Path:
        return self.entries_dir / f"{fingerprint}.json"

    def _history_path(self, fingerprint: str, run_id: str) -> Path:
        return self.history_dir / fingerprint / f"{run_id}.json"

    def get_entry_path(self, fingerprint: str) -> str:
        return str(self._entry_path(fingerprint))

    def get_by_fingerprint(self, fingerprint: str) -> SchemaCacheEntry | None:
        entry_path = self._entry_path(fingerprint)
        if not entry_path.exists():
            return None
        payload = json.loads(entry_path.read_text(encoding="utf-8"))
        return SchemaCacheEntry.model_validate(payload)

    def upsert_candidate(
        self,
        fingerprint: SchemaFingerprint,
        canonical_schema_name: str,
        planner_output: AgentResponse,
        run_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = metadata or {}
        now = _utc_now_iso()
        planner_output_payload = planner_output.model_dump()
        planner_output_hash = _hash_planner_output(planner_output_payload)
        existing_entry = self.get_by_fingerprint(fingerprint.schema_fingerprint_sha256)

        if existing_entry is None:
            entry = SchemaCacheEntry(
                id=fingerprint.schema_fingerprint_sha256,
                schema_fingerprint_sha256=fingerprint.schema_fingerprint_sha256,
                schema_signature_payload=fingerprint.schema_signature_payload,
                canonical_schema_name=canonical_schema_name,
                planner_output=planner_output_payload,
                planner_output_hash=planner_output_hash,
                first_seen_at=now,
                last_seen_at=now,
                use_count=1,
                created_from_run_id=run_id,
                last_used_run_id=run_id,
                metadata=metadata,
            )
            action = "created"
        else:
            entry = existing_entry.model_copy(deep=True)
            entry.schema_signature_payload = fingerprint.schema_signature_payload
            entry.canonical_schema_name = canonical_schema_name
            entry.planner_output = planner_output_payload
            entry.planner_output_hash = planner_output_hash
            entry.last_seen_at = now
            entry.last_used_run_id = run_id
            entry.use_count = max(entry.use_count, 0) + 1
            entry.metadata = {**entry.metadata, **metadata}
            action = "updated"

        entry_path = self._entry_path(fingerprint.schema_fingerprint_sha256)
        entry_path.parent.mkdir(parents=True, exist_ok=True)
        entry_path.write_text(entry.model_dump_json(indent=2), encoding="utf-8")

        history_path = self._history_path(fingerprint.schema_fingerprint_sha256, run_id)
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.write_text(entry.model_dump_json(indent=2), encoding="utf-8")

        return {
            "action": action,
            "root_dir": str(self.root_dir),
            "entry_path": str(entry_path),
            "history_path": str(history_path),
            "approval_status": entry.approval_status,
            "planner_output_hash": planner_output_hash,
            "schema_fingerprint_sha256": fingerprint.schema_fingerprint_sha256,
        }

    def record_usage(
        self,
        entry: SchemaCacheEntry,
        run_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = metadata or {}
        now = _utc_now_iso()
        updated_entry = entry.model_copy(deep=True)
        updated_entry.last_seen_at = now
        updated_entry.last_used_run_id = run_id
        updated_entry.use_count = max(updated_entry.use_count, 0) + 1
        updated_entry.metadata = {**updated_entry.metadata, **metadata}

        entry_path = self._entry_path(updated_entry.schema_fingerprint_sha256)
        entry_path.parent.mkdir(parents=True, exist_ok=True)
        entry_path.write_text(updated_entry.model_dump_json(indent=2), encoding="utf-8")

        history_path = self._history_path(updated_entry.schema_fingerprint_sha256, run_id)
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.write_text(updated_entry.model_dump_json(indent=2), encoding="utf-8")

        return {
            "action": "usage_recorded",
            "root_dir": str(self.root_dir),
            "entry_path": str(entry_path),
            "history_path": str(history_path),
            "approval_status": updated_entry.approval_status,
            "planner_output_hash": updated_entry.planner_output_hash,
            "schema_fingerprint_sha256": updated_entry.schema_fingerprint_sha256,
            "use_count": updated_entry.use_count,
        }