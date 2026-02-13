from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DocumentRecord:
    id: str
    identifier: str
    path: str
    source: str
    kind: str


@dataclass
class TextChunk:
    document_id: str
    location_type: str
    location_value: str
    text: str


@dataclass
class NormalizationResult:
    value: str | None
    success: bool
    reason: str
