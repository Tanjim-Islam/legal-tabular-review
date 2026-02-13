from __future__ import annotations

import json

from src.domain import DocumentRecord, TextChunk
from src.extraction.extractor import extract_field
from src.extraction.normalizers import normalize_currency, normalize_date
from src.extraction.template import load_template
from src.services.run_service import REQUIRED_V1_KEYS
from src.settings import DEFAULT_TEMPLATE_PATH


def _sample_doc() -> DocumentRecord:
    return DocumentRecord(
        id="doc-1",
        identifier="sample.txt",
        path="/tmp/sample.txt",
        source="data",
        kind="txt",
    )


def test_template_has_required_v1_keys_in_order() -> None:
    template = load_template(DEFAULT_TEMPLATE_PATH)
    assert [field.key for field in template.fields] == REQUIRED_V1_KEYS


def test_effective_date_term_combines_components() -> None:
    template = load_template(DEFAULT_TEMPLATE_PATH)
    field = next(f for f in template.fields if f.key == "effective_date_term")

    chunks = [
        TextChunk(
            document_id="doc-1",
            location_type="section",
            location_value="Section 1",
            text=(
                "This Agreement is entered into effective as of October 1, 2014. "
                "Term and Termination: The term is five years from the Effective Date."
            ),
        )
    ]

    result = extract_field(field, _sample_doc(), chunks)

    assert result.value_raw is not None
    assert result.value_normalized is not None

    raw_payload = json.loads(result.value_raw)
    normalized_payload = json.loads(result.value_normalized)

    assert raw_payload["effective_date"]
    assert raw_payload["term"]
    assert normalized_payload["effective_date"] == "2014-10-01"
    assert result.citation is not None


def test_payment_delivery_terms_extractor() -> None:
    template = load_template(DEFAULT_TEMPLATE_PATH)
    field = next(f for f in template.fields if f.key == "payment_delivery_terms")

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


def test_breach_liability_extractor() -> None:
    template = load_template(DEFAULT_TEMPLATE_PATH)
    field = next(f for f in template.fields if f.key == "breach_liability")

    chunks = [
        TextChunk(
            document_id="doc-1",
            location_type="section",
            location_value="Section 12",
            text=(
                "Limitation of Liability: Seller shall be liable for direct damages caused by breach, "
                "subject to the liability cap in this Agreement."
            ),
        )
    ]

    result = extract_field(field, _sample_doc(), chunks)

    assert result.value_raw is not None
    assert "liable" in result.value_raw.lower() or "liability" in result.value_raw.lower()


def test_date_normalizer() -> None:
    normalized = normalize_date("January 15, 2025")
    assert normalized.success is True
    assert normalized.value == "2025-01-15"


def test_currency_normalizer() -> None:
    normalized = normalize_currency("USD $1,250.50")
    assert normalized.success is True
    assert normalized.value == "$1250.50"
