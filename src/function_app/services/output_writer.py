from __future__ import annotations

import csv
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
