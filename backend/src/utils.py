from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def from_json(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def compact_whitespace(text: str) -> str:
    return " ".join(text.split())
