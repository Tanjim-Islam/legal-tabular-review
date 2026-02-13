from __future__ import annotations

from src.domain import DocumentRecord, TextChunk
from src.extraction.extractor import extract_field
from src.extraction.normalizers import normalize_currency, normalize_date
from src.extraction.template import load_template
from src.settings import DEFAULT_TEMPLATE_PATH


def _sample_doc() -> DocumentRecord:
    return DocumentRecord(
        id="doc-1",
        identifier="sample.txt",
        path="/tmp/sample.txt",
        source="data",
        kind="txt",
    )


def test_effective_date_extractor_and_date_normalizer() -> None:
    template = load_template(DEFAULT_TEMPLATE_PATH)
    field = next(f for f in template.fields if f.key == "effective_date")

    chunks = [
        TextChunk(
            document_id="doc-1",
            location_type="section",
            location_value="Section 1",
            text="This Agreement is entered into effective as of October 1, 2014 between Alpha and Beta.",
        )
    ]

    result = extract_field(field, _sample_doc(), chunks)

    assert result.value_raw is not None
    assert result.value_normalized == "2014-10-01"
    assert result.citation is not None


def test_payment_terms_extractor() -> None:
    template = load_template(DEFAULT_TEMPLATE_PATH)
    field = next(f for f in template.fields if f.key == "payment_terms")

    chunks = [
        TextChunk(
            document_id="doc-1",
            location_type="section",
            location_value="Section 4",
            text="Invoicing and Payment: Tesla will pay Seller's charges 30 days after receipt of each invoice.",
        )
    ]

    result = extract_field(field, _sample_doc(), chunks)

    assert result.value_raw is not None
    assert "30 days" in result.value_raw.lower()
    assert result.confidence > 0


def test_date_normalizer() -> None:
    normalized = normalize_date("January 15, 2025")
    assert normalized.success is True
    assert normalized.value == "2025-01-15"


def test_currency_normalizer() -> None:
    normalized = normalize_currency("USD $1,250.50")
    assert normalized.success is True
    assert normalized.value == "$1250.50"
