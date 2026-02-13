from __future__ import annotations

import re
from bs4 import BeautifulSoup

from ..domain import DocumentRecord, TextChunk


SECTION_PATTERN = re.compile(
    r"^(ARTICLE\s+[IVXLC0-9]+\b.*|Section\s+[0-9A-Za-z.\-]+\b.*|\d{1,2}\.\s+.+)$",
    flags=re.IGNORECASE,
)


NOISE_PATTERNS = (
    "screenity",
    "boomerang",
    "chrome-extension://",
)


def _looks_like_noise(text: str) -> bool:
    lower = text.lower()
    return any(pattern in lower for pattern in NOISE_PATTERNS)


def _clean_html(raw_html: str) -> BeautifulSoup:
    soup = BeautifulSoup(raw_html, "lxml")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    for tag in list(soup.find_all(True)):
        if tag is None or not hasattr(tag, "get"):
            continue
        try:
            classes_raw = tag.get("class")
            classes = " ".join(classes_raw) if classes_raw else ""
            identifiers = tag.get("id", "")
        except Exception:  # noqa: BLE001
            continue
        blob = f"{classes} {identifiers}".lower()
        if "screenity" in blob:
            tag.decompose()

    return soup


def _to_sections(text: str, document_id: str) -> list[TextChunk]:
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line and not _looks_like_noise(line)]

    sections: list[TextChunk] = []
    current_label = "section_1"
    current_lines: list[str] = []
    section_index = 1

    def flush() -> None:
        nonlocal current_lines, section_index
        if not current_lines:
            return
        body = "\n".join(current_lines).strip()
        if body:
            sections.append(
                TextChunk(
                    document_id=document_id,
                    location_type="section",
                    location_value=current_label,
                    text=body,
                )
            )
        current_lines = []
        section_index += 1

    for line in lines:
        if SECTION_PATTERN.match(line) and len(" ".join(current_lines)) > 250:
            flush()
            current_label = line[:120]
            continue
        current_lines.append(line)

    flush()

    if sections:
        return sections

    joined = "\n".join(lines)
    chunk_size = 4000
    fallback: list[TextChunk] = []
    for idx in range(0, len(joined), chunk_size):
        fallback.append(
            TextChunk(
                document_id=document_id,
                location_type="section",
                location_value=f"section_{idx // chunk_size + 1}",
                text=joined[idx : idx + chunk_size],
            )
        )
    return fallback


def parse_html(document: DocumentRecord) -> list[TextChunk]:
    with open(document.path, "r", encoding="utf-8", errors="replace") as handle:
        raw = handle.read()

    soup = _clean_html(raw)
    text = soup.get_text("\n")
    return _to_sections(text, document.id)
