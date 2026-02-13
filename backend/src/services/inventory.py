from __future__ import annotations

import hashlib
from pathlib import Path

from ..database import store
from ..domain import DocumentRecord
from ..settings import DATA_DIR, UPLOADS_DIR
from ..utils import utc_now_iso

SUPPORTED_EXTENSIONS = {".pdf", ".html", ".htm"}


def _build_document_id(path: Path) -> str:
    digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()
    return digest[:16]


def _scan_directory(directory: Path, source: str) -> list[DocumentRecord]:
    if not directory.exists():
        return []

    records: list[DocumentRecord] = []
    for path in sorted(directory.glob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            continue
        records.append(
            DocumentRecord(
                id=_build_document_id(path),
                identifier=path.name,
                path=str(path.resolve()),
                source=source,
                kind=suffix.lstrip("."),
            )
        )

    return records


def upsert_documents(records: list[DocumentRecord]) -> None:
    now = utc_now_iso()
    rows = [
        (
            doc.id,
            doc.identifier,
            doc.path,
            doc.source,
            doc.kind,
            now,
            now,
        )
        for doc in records
    ]
    store.executemany(
        """
        INSERT INTO documents (id, identifier, path, source, kind, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            identifier=excluded.identifier,
            path=excluded.path,
            source=excluded.source,
            kind=excluded.kind,
            updated_at=excluded.updated_at
        """,
        rows,
    )


def sync_and_list_documents() -> list[DocumentRecord]:
    records = _scan_directory(DATA_DIR, "data") + _scan_directory(UPLOADS_DIR, "upload")
    upsert_documents(records)

    rows = store.fetchall(
        """
        SELECT id, identifier, path, source, kind
        FROM documents
        ORDER BY CASE source WHEN 'data' THEN 0 ELSE 1 END, identifier ASC
        """
    )
    return [
        DocumentRecord(
            id=row["id"],
            identifier=row["identifier"],
            path=row["path"],
            source=row["source"],
            kind=row["kind"],
        )
        for row in rows
    ]
