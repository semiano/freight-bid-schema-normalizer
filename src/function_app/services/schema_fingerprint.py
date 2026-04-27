from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from ..models.contracts import SchemaFingerprint, WorkbookProfile


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    normalized = str(value).strip().lower()
    return re.sub(r"\s+", " ", normalized)


def build_schema_signature_payload(profile: WorkbookProfile) -> dict[str, Any]:
    sheets: list[dict[str, Any]] = []

    for sheet in profile.sheets:
        inferred_types = {
            _normalize_text(column_name): _normalize_text(dtype)
            for column_name, dtype in sorted(
                sheet.inferred_types.items(),
                key=lambda item: _normalize_text(item[0]),
            )
        }
        sheets.append(
            {
                "sheet_name": _normalize_text(sheet.name),
                "visible": bool(sheet.visible),
                "header_row": sheet.header_row,
                "columns": [_normalize_text(column) for column in sheet.columns],
                "inferred_types": inferred_types,
                "likely_business_meaning": _normalize_text(sheet.likely_business_meaning),
                "classifier_hints": sorted(_normalize_text(hint) for hint in sheet.classifier_hints),
            }
        )

    return {
        "sheet_count": len(sheets),
        "sheets": sheets,
    }


def compute_schema_fingerprint(profile: WorkbookProfile) -> SchemaFingerprint:
    signature_payload = build_schema_signature_payload(profile)
    canonical_json = json.dumps(signature_payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return SchemaFingerprint(
        schema_fingerprint_sha256=digest,
        schema_signature_payload=signature_payload,
    )