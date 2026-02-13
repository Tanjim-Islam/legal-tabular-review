from __future__ import annotations

from pypdf import PdfReader

from ..domain import DocumentRecord, TextChunk


def parse_pdf(document: DocumentRecord, max_pages: int | None = None) -> list[TextChunk]:
    reader = PdfReader(document.path)
    chunks: list[TextChunk] = []
    total_pages = len(reader.pages)
    limit = min(total_pages, max_pages) if max_pages else total_pages

    for index in range(limit):
        page = reader.pages[index]
        text = page.extract_text() or ""
        chunks.append(
            TextChunk(
                document_id=document.id,
                location_type="page",
                location_value=str(index + 1),
                text=text,
            )
        )

    return chunks
