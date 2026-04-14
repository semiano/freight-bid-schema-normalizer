from __future__ import annotations

from typing import Any


NON_DATA_KEYWORDS = {
    "requirement": "instructional",
    "requirements": "instructional",
    "instruction": "instructional",
    "readme": "instructional",
    "fsc": "reference",
    "location": "reference",
    "locations": "reference",
    "lookup": "reference",
}


def classify_sheet(sheet_name: str, columns: list[str], sample_rows: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_name = (sheet_name or "").strip().lower()
    hints: list[str] = []
    score = 0

    for keyword, label in NON_DATA_KEYWORDS.items():
        if keyword in normalized_name:
            hints.append(f"name_matches_{label}_{keyword}")
            score -= 3

    non_empty_columns = [column for column in columns if str(column).strip()]
    if len(non_empty_columns) >= 4:
        score += 2
        hints.append("has_multiple_columns")

    non_empty_sample_rows = [
        row for row in sample_rows if any(value not in (None, "") for value in row.values())
    ]
    if len(non_empty_sample_rows) >= 3:
        score += 2
        hints.append("has_non_empty_sample_rows")

    if not non_empty_sample_rows:
        score -= 2
        hints.append("no_data_rows_detected")

    likely_exclude = score < 1
    if any("instructional" in hint for hint in hints):
        business_meaning = "instructional"
    elif any("reference" in hint for hint in hints):
        business_meaning = "reference"
    elif likely_exclude:
        business_meaning = "likely_exclude"
    else:
        business_meaning = "data"

    return {
        "likely_exclude": likely_exclude,
        "business_meaning": business_meaning,
        "hints": hints,
        "score": score,
    }
