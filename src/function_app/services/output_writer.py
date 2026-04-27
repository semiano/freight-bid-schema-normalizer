from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from ..models.contracts import CanonicalSchema
from .normalization_service import normalize_record


def get_canonical_columns(template_schema: CanonicalSchema) -> list[str]:
    return [column.name for column in template_schema.columns]


def normalize_records_to_canonical(
    records: list[dict[str, Any]],
    template_schema: CanonicalSchema,
) -> list[dict[str, Any]]:
    canonical_columns = get_canonical_columns(template_schema)
    bool_columns = {
        column.name
        for column in template_schema.columns
        if column.dtype.strip().lower() == "bool"
    }
    normalized_records: list[dict[str, Any]] = []

    for record in records:
        canonical_projection = {column: record.get(column, "") for column in canonical_columns}
        normalized = normalize_record(canonical_projection, bool_columns=bool_columns)
        normalized_records.append(normalized)

    return normalized_records


def write_canonical_csv(
    records: list[dict[str, Any]],
    template_schema: CanonicalSchema,
    output_path: str,
) -> str:
    canonical_columns = get_canonical_columns(template_schema)
    normalized_records = normalize_records_to_canonical(records, template_schema)

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=canonical_columns)
        writer.writeheader()
        writer.writerows(normalized_records)

    return str(destination)


def write_canonical_xlsx(
    records: list[dict[str, Any]],
    template_schema: CanonicalSchema,
    output_path: str,
    sheet_name: str = "CanonicalOutput",
) -> str:
    canonical_columns = get_canonical_columns(template_schema)
    normalized_records = normalize_records_to_canonical(records, template_schema)

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name

    worksheet.append(canonical_columns)
    for record in normalized_records:
        worksheet.append([record[column] for column in canonical_columns])

    workbook.save(destination)
    return str(destination)


def write_notes_json(
    planner_notes: list[dict[str, Any]],
    sandbox_notes: list[dict[str, Any]],
    output_path: str,
    change_log: list[dict[str, Any]] | None = None,
) -> str:
    """Write the combined notes JSON artifact.

    Merges planner-level notes (from the agent response ``notes_json``)
    with runtime notes extracted from the sandbox transform ``notes`` list,
    and optionally includes a post-process change log.
    """
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    combined: list[dict[str, Any]] = []

    for note in planner_notes:
        entry = dict(note)
        entry.setdefault("origin", "planner")
        combined.append(entry)

    for note in sandbox_notes:
        entry = dict(note)
        entry.setdefault("origin", "transform")
        combined.append(entry)

    change_log = change_log or []

    payload = {
        "total_notes": len(combined),
        "planner_note_count": len(planner_notes),
        "transform_note_count": len(sandbox_notes),
        "notes": combined,
        "post_process_change_log": {
            "total_updates": len(change_log),
            "fields_updated": list({c["field"] for c in change_log}),
            "changes": change_log,
        },
    }

    with destination.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)

    return str(destination)
