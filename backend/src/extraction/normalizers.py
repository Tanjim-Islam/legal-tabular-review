from __future__ import annotations

from datetime import date
import re
from dateutil import parser as date_parser

from ..domain import NormalizationResult
from ..utils import compact_whitespace


CURRENCY_PATTERN = re.compile(r"(?P<symbol>\$)?\s*(?P<amount>[0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)")


def normalize_text(value: str) -> NormalizationResult:
    cleaned = compact_whitespace(value)
    return NormalizationResult(value=cleaned if cleaned else None, success=bool(cleaned), reason="text_cleanup")


def normalize_date(value: str) -> NormalizationResult:
    try:
        parsed = date_parser.parse(value, fuzzy=True, dayfirst=False).date()
        if not isinstance(parsed, date):
            return NormalizationResult(value=None, success=False, reason="date_parse_failed")
        return NormalizationResult(value=parsed.isoformat(), success=True, reason="date_parsed")
    except (ValueError, OverflowError):
        return NormalizationResult(value=None, success=False, reason="date_parse_failed")


def normalize_currency(value: str) -> NormalizationResult:
    match = CURRENCY_PATTERN.search(value)
    if not match:
        return NormalizationResult(value=None, success=False, reason="currency_parse_failed")

    amount = match.group("amount").replace(",", "")
    symbol = match.group("symbol") or ""
    normalized = f"{symbol}{amount}"
    return NormalizationResult(value=normalized, success=True, reason="currency_parsed")


NORMALIZERS = {
    "text": normalize_text,
    "date": normalize_date,
    "currency": normalize_currency,
}


def normalize_value(value: str, normalizer_name: str) -> NormalizationResult:
    normalizer = NORMALIZERS.get(normalizer_name, normalize_text)
    return normalizer(value)
