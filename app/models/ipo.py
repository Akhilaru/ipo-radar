from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class IpoType(StrEnum):
    MAINBOARD = "mainboard"
    SME = "sme"


class IpoStatus(StrEnum):
    UPCOMING = "upcoming"
    OPEN = "open"
    CLOSED = "closed"
    LISTED = "listed"
    UNKNOWN = "unknown"


class Ipo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: int | None = None
    external_id: str | None = None
    slug: str | None = None
    company_name: str = Field(min_length=1)
    symbol: str | None = None
    ipo_type: IpoType = IpoType.MAINBOARD
    exchange: str | None = None
    open_date: date | None = None
    close_date: date | None = None
    allotment_date: date | None = None
    listing_date: date | None = None
    price_low: float | None = Field(default=None, ge=0)
    price_high: float | None = Field(default=None, ge=0)
    lot_size: int | None = Field(default=None, gt=0)
    issue_size: float | None = Field(default=None, ge=0)
    status: IpoStatus = IpoStatus.UNKNOWN
    created_at: datetime | None = None
    updated_at: datetime | None = None

