from __future__ import annotations

from ..domain import DocumentRecord, TextChunk
from .html_parser import parse_html
from .pdf_parser import parse_pdf


def parse_document(document: DocumentRecord, max_pages: int | None = None) -> list[TextChunk]:
    if document.kind == "pdf":
        return parse_pdf(document, max_pages=max_pages)
    if document.kind in {"html", "htm"}:
        return parse_html(document)
    raise ValueError(f"Unsupported document type: {document.kind}")
