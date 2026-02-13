from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    mode: Literal["quick", "full"] = "quick"
    wait: bool = Field(default=False, description="When true, execute the job before returning.")
    template_path: str | None = None


class CellUpdateRequest(BaseModel):
    actor: str = "reviewer"
    review_state: Literal["CONFIRMED", "REJECTED", "MANUAL_UPDATED", "MISSING_DATA"] | None = None
    manual_value: str | None = None
    reason: str | None = None


class ExportRequest(BaseModel):
    job_id: str | None = None
