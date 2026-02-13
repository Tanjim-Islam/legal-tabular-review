from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass
class FieldSearchConfig:
    patterns: list[str]
    join_groups: bool = False


@dataclass
class FieldTemplate:
    key: str
    label: str
    field_type: str
    normalizer: str
    hints: list[str]
    search: FieldSearchConfig


@dataclass
class ExtractionTemplate:
    template_id: str
    status: str
    description: str
    fields: list[FieldTemplate]


def load_template(path: str | Path) -> ExtractionTemplate:
    template_path = Path(path)
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    fields = []

    for raw_field in payload["fields"]:
        search_payload = raw_field.get("search", {})
        fields.append(
            FieldTemplate(
                key=raw_field["key"],
                label=raw_field.get("label", raw_field["key"]),
                field_type=raw_field.get("type", "text"),
                normalizer=raw_field.get("normalizer", "text"),
                hints=raw_field.get("hints", []),
                search=FieldSearchConfig(
                    patterns=search_payload.get("patterns", []),
                    join_groups=bool(search_payload.get("join_groups", False)),
                ),
            )
        )

    return ExtractionTemplate(
        template_id=payload.get("template_id", template_path.stem),
        status=payload.get("status", "unknown"),
        description=payload.get("description", ""),
        fields=fields,
    )
