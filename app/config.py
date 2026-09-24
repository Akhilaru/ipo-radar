"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class Settings:
    timezone: ZoneInfo
    database_path: Path
    ipoguru_api_key: str | None
    ipoguru_daily_limit: int
    ipoguru_min_request_interval_seconds: int
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    openrouter_api_key: str | None
    openrouter_model: str | None
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        timezone_name = os.getenv("TIMEZONE", "Asia/Kolkata")
        return cls(
            timezone=ZoneInfo(timezone_name),
            database_path=Path(os.getenv("DATABASE_PATH", "data/ipo_radar.db")),
            ipoguru_api_key=_optional("IPOGURU_API_KEY"),
            ipoguru_daily_limit=_int("IPOGURU_DAILY_LIMIT", 10),
            ipoguru_min_request_interval_seconds=_int("IPOGURU_MIN_REQUEST_INTERVAL_SECONDS", 60),
            telegram_bot_token=_optional("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_optional("TELEGRAM_CHAT_ID"),
            openrouter_api_key=_optional("OPENROUTER_API_KEY"),
            openrouter_model=_optional("OPENROUTER_MODEL"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )


def _optional(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default

