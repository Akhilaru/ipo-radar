from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SubscriptionObservation(BaseModel):
    ipo_id: int
    retail: float | None = Field(default=None, ge=0)
    nii: float | None = Field(default=None, ge=0)
    qib: float | None = Field(default=None, ge=0)
    employee: float | None = Field(default=None, ge=0)
    other: float | None = Field(default=None, ge=0)
    total: float | None = Field(default=None, ge=0)
    source: str = Field(min_length=1)
    retrieved_at: datetime
    source_updated_at: datetime | None = None

