from __future__ import annotations

from pathlib import Path

from src.domain import DocumentRecord
from src.parsers.pdf_parser import parse_pdf


def test_pdf_parser_extracts_first_pages() -> None:
    path = Path(__file__).resolve().parents[3] / "data" / "Supply Agreement.pdf"
    document = DocumentRecord(
        id="doc-test-pdf",
        identifier=path.name,
        path=str(path),
        source="data",
        kind="pdf",
    )

    chunks = parse_pdf(document, max_pages=2)

    assert len(chunks) == 2
    assert all(chunk.location_type == "page" for chunk in chunks)
    assert chunks[0].location_value == "1"
    assert "agreement" in chunks[0].text.lower()
