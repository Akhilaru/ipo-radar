from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNAVAILABLE = "unavailable"


class SentimentAnalysis(BaseModel):
    ipo_id: int
    article_hash: str | None = None
    sentiment: Sentiment
    sentiment_score: int | None = Field(default=None, ge=0, le=10)
    positives: list[str] = []
    risks: list[str] = []
    summary: str | None = None
    model: str | None = None
    analyzed_at: datetime

