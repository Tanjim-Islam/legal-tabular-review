from __future__ import annotations

from pathlib import Path

from src.domain import DocumentRecord
from src.parsers.html_parser import parse_html


def test_html_parser_extracts_sections_and_strips_noise() -> None:
    path = Path(__file__).resolve().parents[3] / "data" / "EX-10.2.html"
    document = DocumentRecord(
        id="doc-test-html",
        identifier=path.name,
        path=str(path),
        source="data",
        kind="html",
    )

    chunks = parse_html(document)

    assert len(chunks) > 1
    joined = "\n".join(chunk.text for chunk in chunks).lower()
    assert "effective date" in joined
    assert "screenitydropdownmenu" not in joined
