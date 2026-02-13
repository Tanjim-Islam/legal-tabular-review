from __future__ import annotations

import csv
from pathlib import Path
from typing import Any
from openpyxl import Workbook

from ..settings import EXPORTS_DIR
from ..utils import utc_now_iso
from .run_service import get_table_payload


def _build_rows(table_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for row in table_payload.get("rows", []):
        for cell in row.get("cells", []):
            citation = cell.get("citation") or {}
            rows.append(
                {
                    "field_key": row["field_key"],
                    "field_label": row["field_label"],
                    "field_type": row["field_type"],
                    "document_identifier": cell.get("document_identifier"),
                    "value": cell.get("value"),
                    "value_raw": cell.get("value_raw"),
                    "value_normalized": cell.get("value_normalized"),
                    "review_state": cell.get("review_state"),
                    "confidence": cell.get("confidence"),
                    "citation_location": citation.get("location"),
                    "citation_location_type": citation.get("location_type"),
                    "citation_char_start": citation.get("char_start"),
                    "citation_char_end": citation.get("char_end"),
                    "citation_snippet": citation.get("snippet"),
                }
            )
    return rows


def export_csv(job_id: str | None = None) -> Path:
    payload = get_table_payload(job_id)
    rows = _build_rows(payload)
    filename = f"legal_review_{payload.get('job', {}).get('id', 'none')}_{utc_now_iso().replace(':', '-')}.csv"
    target = EXPORTS_DIR / filename

    columns = [
        "field_key",
        "field_label",
        "field_type",
        "document_identifier",
        "value",
        "value_raw",
        "value_normalized",
        "review_state",
        "confidence",
        "citation_location",
        "citation_location_type",
        "citation_char_start",
        "citation_char_end",
        "citation_snippet",
    ]

    with open(target, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return target


def export_xlsx(job_id: str | None = None) -> Path:
    payload = get_table_payload(job_id)
    rows = _build_rows(payload)

    filename = f"legal_review_{payload.get('job', {}).get('id', 'none')}_{utc_now_iso().replace(':', '-')}.xlsx"
    target = EXPORTS_DIR / filename

    columns = [
        "field_key",
        "field_label",
        "field_type",
        "document_identifier",
        "value",
        "value_raw",
        "value_normalized",
        "review_state",
        "confidence",
        "citation_location",
        "citation_location_type",
        "citation_char_start",
        "citation_char_end",
        "citation_snippet",
    ]

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "review_table"

    sheet.append(columns)
    for row in rows:
        sheet.append([row[column] for column in columns])

    workbook.save(target)
    return target
