from __future__ import annotations

import threading
import uuid
from typing import Any

from ..database import store
from ..domain import DocumentRecord
from ..extraction.extractor import ExtractionResult, extract_field
from ..extraction.template import ExtractionTemplate, load_template
from ..parsers import parse_document
from ..settings import DEFAULT_TEMPLATE_PATH
from ..utils import from_json, to_json, utc_now_iso
from .inventory import sync_and_list_documents

REQUIRED_V1_KEYS = [
    "parties_and_entities",
    "effective_date_term",
    "dispute_resolution",
    "breach_liability",
    "payment_delivery_terms",
]


def create_job(mode: str, options: dict[str, Any]) -> str:
    job_id = uuid.uuid4().hex
    store.execute(
        """
        INSERT INTO jobs (id, mode, status, error_message, options_json, created_at)
        VALUES (?, ?, 'QUEUED', NULL, ?, ?)
        """,
        (job_id, mode, to_json(options), utc_now_iso()),
    )
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    row = store.fetchone(
        """
        SELECT id, mode, status, error_message, options_json, created_at, started_at, finished_at
        FROM jobs
        WHERE id = ?
        """,
        (job_id,),
    )
    if row is None:
        return None
    return {
        "id": row["id"],
        "mode": row["mode"],
        "status": row["status"],
        "error_message": row["error_message"],
        "options": from_json(row["options_json"], {}),
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }


def _set_job_running(job_id: str) -> None:
    store.execute(
        "UPDATE jobs SET status = 'RUNNING', started_at = ? WHERE id = ?",
        (utc_now_iso(), job_id),
    )


def _set_job_failed(job_id: str, message: str) -> None:
    store.execute(
        "UPDATE jobs SET status = 'FAILED', error_message = ?, finished_at = ? WHERE id = ?",
        (message, utc_now_iso(), job_id),
    )


def _set_job_completed(job_id: str) -> None:
    store.execute(
        "UPDATE jobs SET status = 'COMPLETED', finished_at = ? WHERE id = ?",
        (utc_now_iso(), job_id),
    )


def _insert_cells(job_id: str, document: DocumentRecord, results: list[ExtractionResult]) -> None:
    now = utc_now_iso()
    rows = []
    for result in results:
        rows.append(
            (
                uuid.uuid4().hex,
                job_id,
                result.field_key,
                result.field_label,
                result.field_type,
                document.id,
                document.identifier,
                result.value_raw,
                result.value_normalized,
                result.confidence,
                to_json(result.confidence_reasons),
                result.review_state,
                to_json(result.citation),
                to_json(result.extraction_meta),
                now,
                now,
            )
        )

    store.executemany(
        """
        INSERT INTO cells (
            id, job_id, field_key, field_label, field_type, document_id, document_identifier,
            value_raw, value_normalized, confidence, confidence_reasons_json, review_state,
            citation_json, extraction_meta_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def _extract_for_document(document: DocumentRecord, mode: str, fields: list[Any]) -> list[ExtractionResult]:
    max_pages = 3 if mode == "quick" and document.kind == "pdf" else None

    try:
        chunks = parse_document(document, max_pages=max_pages)
    except Exception as exc:  # noqa: BLE001
        return [
            ExtractionResult(
                field_key=field.key,
                field_label=field.label,
                field_type=field.field_type,
                value_raw=None,
                value_normalized=None,
                confidence=0.0,
                confidence_reasons=["parse_failed"],
                review_state="MISSING_DATA",
                citation=None,
                extraction_meta={"error": str(exc)},
            )
            for field in fields
        ]

    return [extract_field(field, document, chunks) for field in fields]


def run_job_sync(job_id: str, mode: str, template_path: str | None = None) -> None:
    _set_job_running(job_id)

    try:
        documents = sync_and_list_documents()
        if not documents:
            raise RuntimeError("No supported documents found in data/uploads")

        selected_documents = documents[:1] if mode == "quick" else documents

        effective_template_path = template_path or str(DEFAULT_TEMPLATE_PATH)
        template = load_template(effective_template_path)
        fields = template.fields[:5] if mode == "quick" else template.fields

        store.execute("DELETE FROM cells WHERE job_id = ?", (job_id,))

        for document in selected_documents:
            extracted = _extract_for_document(document, mode, fields)
            _insert_cells(job_id, document, extracted)

        _set_job_completed(job_id)
    except Exception as exc:  # noqa: BLE001
        _set_job_failed(job_id, str(exc))


def run_job_async(job_id: str, mode: str, template_path: str | None = None) -> None:
    thread = threading.Thread(target=run_job_sync, args=(job_id, mode, template_path), daemon=True)
    thread.start()


def get_latest_completed_job_id() -> str | None:
    row = store.fetchone(
        """
        SELECT id
        FROM jobs
        WHERE status = 'COMPLETED'
        ORDER BY finished_at DESC
        LIMIT 1
        """
    )
    return row["id"] if row else None


def _row_to_cell(row: Any) -> dict[str, Any]:
    return {
        "cell_id": row["id"],
        "document_id": row["document_id"],
        "document_identifier": row["document_identifier"],
        "value": row["value_normalized"] or row["value_raw"],
        "value_raw": row["value_raw"],
        "value_normalized": row["value_normalized"],
        "review_state": row["review_state"],
        "confidence": row["confidence"],
        "confidence_reasons": from_json(row["confidence_reasons_json"], []),
        "citation": from_json(row["citation_json"], None),
        "extraction_meta": from_json(row["extraction_meta_json"], {}),
    }


def _resolve_template_for_payload(job_id: str | None) -> ExtractionTemplate:
    template_path = str(DEFAULT_TEMPLATE_PATH)
    if job_id:
        job = get_job(job_id)
        if job:
            options = job.get("options", {}) or {}
            template_path = options.get("template_path") or template_path

    return load_template(template_path)


def get_table_payload(job_id: str | None = None) -> dict[str, Any]:
    effective_job_id = job_id or get_latest_completed_job_id()
    template = _resolve_template_for_payload(effective_job_id)
    field_order_map = {field.key: index for index, field in enumerate(template.fields)}

    if not effective_job_id:
        return {
            "job": None,
            "documents": [],
            "fields": [],
            "rows": [],
        }

    job = get_job(effective_job_id)
    rows = store.fetchall(
        """
        SELECT *
        FROM cells
        WHERE job_id = ?
        ORDER BY document_identifier ASC
        """,
        (effective_job_id,),
    )

    if not rows:
        return {
            "job": job,
            "documents": [],
            "fields": [],
            "rows": [],
        }

    documents: list[dict[str, Any]] = []
    document_ids: list[str] = []
    fields: list[dict[str, Any]] = []
    field_keys: list[str] = []

    for row in rows:
        if row["document_id"] not in document_ids:
            document_ids.append(row["document_id"])
            documents.append(
                {
                    "id": row["document_id"],
                    "identifier": row["document_identifier"],
                }
            )

        if row["field_key"] not in field_keys:
            field_keys.append(row["field_key"])
            fields.append(
                {
                    "key": row["field_key"],
                    "label": row["field_label"],
                    "type": row["field_type"],
                }
            )

    fields.sort(key=lambda item: field_order_map.get(item["key"], 9999))

    cell_map: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        cell_map[(row["field_key"], row["document_id"])] = _row_to_cell(row)

    table_rows: list[dict[str, Any]] = []
    for field in fields:
        cells = []
        for document in documents:
            key = (field["key"], document["id"])
            cell = cell_map.get(
                key,
                {
                    "cell_id": None,
                    "document_id": document["id"],
                    "document_identifier": document["identifier"],
                    "value": None,
                    "value_raw": None,
                    "value_normalized": None,
                    "review_state": "MISSING_DATA",
                    "confidence": 0.0,
                    "confidence_reasons": ["missing"],
                    "citation": None,
                    "extraction_meta": {},
                },
            )
            cells.append(cell)

        table_rows.append(
            {
                "field_key": field["key"],
                "field_label": field["label"],
                "field_type": field["type"],
                "cells": cells,
            }
        )

    return {
        "job": job,
        "documents": documents,
        "fields": fields,
        "rows": table_rows,
    }
