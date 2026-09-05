from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GmpObservation(BaseModel):
    ipo_id: int
    gmp: float = Field(ge=0)
    gmp_percentage: float | None = None
    source: str = Field(min_length=1)
    retrieved_at: datetime
    source_updated_at: datetime | None = None

