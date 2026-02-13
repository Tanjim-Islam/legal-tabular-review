from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from ..domain import DocumentRecord, TextChunk
from ..utils import compact_whitespace
from .normalizers import normalize_value
from .template import FieldTemplate


@dataclass
class ExtractionResult:
    field_key: str
    field_label: str
    field_type: str
    value_raw: str | None
    value_normalized: str | None
    confidence: float
    confidence_reasons: list[str]
    review_state: str
    citation: dict[str, Any] | None
    extraction_meta: dict[str, Any]


@dataclass
class Candidate:
    pattern_index: int
    match_start: int
    match_end: int
    raw_value: str
    snippet: str
    chunk: TextChunk
    hint_match: bool


def _pick_value(match: re.Match[str], join_groups: bool) -> str:
    groups = [group.strip() for group in match.groups() if group and group.strip()]
    if groups:
        return " / ".join(groups) if join_groups else groups[0]
    return match.group(0).strip()


def _make_snippet(text: str, start: int, end: int, radius: int = 140) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return compact_whitespace(text[left:right])


def _to_citation(document: DocumentRecord, candidate: Candidate) -> dict[str, Any]:
    return {
        "document_id": document.id,
        "document_identifier": document.identifier,
        "location_type": candidate.chunk.location_type,
        "location": candidate.chunk.location_value,
        "snippet": candidate.snippet,
        "char_start": candidate.match_start,
        "char_end": candidate.match_end,
        "coordinates": None,
    }


def _missing_result(field: FieldTemplate, document: DocumentRecord, reason: str = "no_match") -> ExtractionResult:
    return ExtractionResult(
        field_key=field.key,
        field_label=field.label,
        field_type=field.field_type,
        value_raw=None,
        value_normalized=None,
        confidence=0.0,
        confidence_reasons=[reason],
        review_state="MISSING_DATA",
        citation=None,
        extraction_meta={"candidate_count": 0, "document_id": document.id},
    )


def _collect_candidates(field: FieldTemplate, chunks: list[TextChunk]) -> list[Candidate]:
    candidates: list[Candidate] = []

    for pattern_index, pattern in enumerate(field.search.patterns):
        regex = re.compile(pattern, flags=re.IGNORECASE | re.MULTILINE)
        for chunk in chunks:
            hint_blob = f"{chunk.location_value}\n{chunk.text[:1200]}".lower()
            hint_match = any(hint.lower() in hint_blob for hint in field.hints)
            for match in regex.finditer(chunk.text):
                raw_value = _pick_value(match, field.search.join_groups)
                raw_value = compact_whitespace(raw_value)
                if not raw_value:
                    continue

                candidates.append(
                    Candidate(
                        pattern_index=pattern_index,
                        match_start=match.start(),
                        match_end=match.end(),
                        raw_value=raw_value,
                        snippet=_make_snippet(chunk.text, match.start(), match.end()),
                        chunk=chunk,
                        hint_match=hint_match,
                    )
                )

    candidates.sort(key=lambda c: (c.pattern_index, -int(c.hint_match), c.match_start, -len(c.raw_value)))
    return candidates


def _score_candidates(field: FieldTemplate, candidates: list[Candidate], normalized_success: bool) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.5

    if not candidates:
        return 0.0, ["no_match"]

    best = candidates[0]
    reasons.append(f"pattern_{best.pattern_index + 1}")

    if len(candidates) == 1:
        score += 0.25
        reasons.append("single_candidate")
    else:
        score -= 0.15
        reasons.append("multiple_candidates")

    if best.pattern_index == 0:
        score += 0.1
        reasons.append("primary_pattern")

    if best.hint_match:
        score += 0.05
        reasons.append("hint_context")

    if normalized_success:
        score += 0.1
        reasons.append("normalized")
    else:
        score -= 0.05
        reasons.append("normalization_failed")

    score = max(0.05, min(score, 0.99))
    return round(score, 3), reasons


def _extract_effective_date_term(field: FieldTemplate, document: DocumentRecord, chunks: list[TextChunk]) -> ExtractionResult:
    candidates = _collect_candidates(field, chunks)
    if not candidates:
        return _missing_result(field, document)

    date_candidates: list[tuple[Candidate, str]] = []
    non_date_candidates: list[Candidate] = []

    for candidate in candidates:
        normalized_date = normalize_value(candidate.raw_value, "date")
        if normalized_date.success and normalized_date.value:
            date_candidates.append((candidate, normalized_date.value))
        else:
            non_date_candidates.append(candidate)

    term_candidates = [
        candidate
        for candidate in non_date_candidates
        if any(token in f"{candidate.raw_value} {candidate.snippet}".lower() for token in ["term", "termination", "lease term", "renewal"])
    ]

    date_best = date_candidates[0] if date_candidates else None
    term_best = term_candidates[0] if term_candidates else (non_date_candidates[0] if non_date_candidates else None)

    if not date_best and not term_best:
        best = candidates[0]
        normalized = normalize_value(best.raw_value, field.normalizer)
        confidence, reasons = _score_candidates(field, candidates, normalized.success)
        return ExtractionResult(
            field_key=field.key,
            field_label=field.label,
            field_type=field.field_type,
            value_raw=best.raw_value,
            value_normalized=normalized.value,
            confidence=confidence,
            confidence_reasons=reasons,
            review_state="CONFIRMED",
            citation=_to_citation(document, best),
            extraction_meta={
                "candidate_count": len(candidates),
                "mode": "fallback_single_value",
            },
        )

    raw_payload = {
        "effective_date": date_best[0].raw_value if date_best else None,
        "term": term_best.raw_value if term_best else None,
    }
    normalized_payload = {
        "effective_date": date_best[1] if date_best else None,
        "term": term_best.raw_value if term_best else None,
    }

    citation_candidate = date_best[0] if date_best else term_best
    if citation_candidate is None:
        return _missing_result(field, document)

    confidence = 0.45
    reasons: list[str] = []
    if date_best:
        confidence += 0.25
        reasons.append("effective_date_found")
    else:
        reasons.append("effective_date_missing")

    if term_best:
        confidence += 0.2
        reasons.append("term_found")
    else:
        reasons.append("term_missing")

    if len(candidates) > 4:
        confidence -= 0.1
        reasons.append("multiple_candidates")
    else:
        reasons.append("candidate_set_small")

    if date_best and term_best and date_best[0].chunk.location_value == term_best.chunk.location_value:
        confidence += 0.05
        reasons.append("same_location")

    confidence = round(max(0.05, min(confidence, 0.99)), 3)

    return ExtractionResult(
        field_key=field.key,
        field_label=field.label,
        field_type=field.field_type,
        value_raw=json.dumps(raw_payload, ensure_ascii=True),
        value_normalized=json.dumps(normalized_payload, ensure_ascii=True),
        confidence=confidence,
        confidence_reasons=reasons,
        review_state="CONFIRMED",
        citation=_to_citation(document, citation_candidate),
        extraction_meta={
            "candidate_count": len(candidates),
            "mode": "combined_effective_date_term",
            "date_candidate_count": len(date_candidates),
            "term_candidate_count": len(term_candidates) if term_candidates else len(non_date_candidates),
        },
    )


def extract_field(field: FieldTemplate, document: DocumentRecord, chunks: list[TextChunk]) -> ExtractionResult:
    if field.key == "effective_date_term":
        return _extract_effective_date_term(field, document, chunks)

    candidates = _collect_candidates(field, chunks)
    if not candidates:
        return _missing_result(field, document)

    best = candidates[0]
    normalized = normalize_value(best.raw_value, field.normalizer)
    confidence, reasons = _score_candidates(field, candidates, normalized.success)

    return ExtractionResult(
        field_key=field.key,
        field_label=field.label,
        field_type=field.field_type,
        value_raw=best.raw_value,
        value_normalized=normalized.value,
        confidence=confidence,
        confidence_reasons=reasons,
        review_state="CONFIRMED",
        citation=_to_citation(document, best),
        extraction_meta={
            "candidate_count": len(candidates),
            "selected_pattern_index": best.pattern_index,
            "normalizer": field.normalizer,
            "normalization_reason": normalized.reason,
            "template_hints": field.hints,
        },
    )
