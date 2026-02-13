from __future__ import annotations

import uuid
from typing import Any

from ..database import store
from ..utils import to_json, utc_now_iso


ALLOWED_REVIEW_STATES = {"CONFIRMED", "REJECTED", "MANUAL_UPDATED", "MISSING_DATA"}


def update_cell(
    cell_id: str,
    actor: str,
    review_state: str | None = None,
    manual_value: str | None = None,
    reason: str | None = None,
) -> dict[str, Any] | None:
    row = store.fetchone("SELECT * FROM cells WHERE id = ?", (cell_id,))
    if row is None:
        return None

    old_value = row["value_normalized"] or row["value_raw"]
    old_review_state = row["review_state"]

    next_review_state = review_state or row["review_state"]
    next_raw = row["value_raw"]
    next_normalized = row["value_normalized"]

    if manual_value is not None:
        next_raw = manual_value
        next_normalized = manual_value
        next_review_state = "MANUAL_UPDATED"

    if next_review_state not in ALLOWED_REVIEW_STATES:
        raise ValueError(f"Invalid review_state: {next_review_state}")

    now = utc_now_iso()

    meta = {
        "manual_update": manual_value is not None,
        "reason": reason,
    }

    store.execute(
        """
        UPDATE cells
        SET value_raw = ?, value_normalized = ?, review_state = ?, extraction_meta_json = ?, updated_at = ?
        WHERE id = ?
        """,
        (next_raw, next_normalized, next_review_state, to_json(meta), now, cell_id),
    )

    store.execute(
        """
        INSERT INTO audit_logs (
            id, cell_id, action, actor, old_value, new_value, old_review_state, new_review_state, reason, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid.uuid4().hex,
            cell_id,
            "CELL_UPDATED",
            actor,
            old_value,
            next_normalized or next_raw,
            old_review_state,
            next_review_state,
            reason,
            now,
        ),
    )

    updated = store.fetchone("SELECT * FROM cells WHERE id = ?", (cell_id,))
    if updated is None:
        return None

    return {
        "cell_id": updated["id"],
        "value_raw": updated["value_raw"],
        "value_normalized": updated["value_normalized"],
        "review_state": updated["review_state"],
        "updated_at": updated["updated_at"],
    }


def get_audit_logs(cell_id: str) -> list[dict[str, Any]]:
    rows = store.fetchall(
        """
        SELECT id, action, actor, old_value, new_value, old_review_state, new_review_state, reason, created_at
        FROM audit_logs
        WHERE cell_id = ?
        ORDER BY created_at ASC
        """,
        (cell_id,),
    )

    return [
        {
            "id": row["id"],
            "action": row["action"],
            "actor": row["actor"],
            "old_value": row["old_value"],
            "new_value": row["new_value"],
            "old_review_state": row["old_review_state"],
            "new_review_state": row["new_review_state"],
            "reason": row["reason"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
