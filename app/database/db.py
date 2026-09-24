"""SQLite schema and connection lifecycle."""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS ipos (
    id INTEGER PRIMARY KEY,
    external_id TEXT UNIQUE,
    slug TEXT,
    company_name TEXT NOT NULL,
    symbol TEXT,
    ipo_type TEXT NOT NULL,
    exchange TEXT,
    open_date TEXT,
    close_date TEXT,
    allotment_date TEXT,
    listing_date TEXT,
    price_low REAL,
    price_high REAL,
    lot_size INTEGER,
    issue_size REAL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gmp_history (
    id INTEGER PRIMARY KEY,
    ipo_id INTEGER NOT NULL REFERENCES ipos(id),
    gmp REAL NOT NULL,
    gmp_percentage REAL,
    estimated_listing_price REAL,
    source TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    source_updated_at TEXT,
    UNIQUE(ipo_id, source, source_updated_at)
);
CREATE TABLE IF NOT EXISTS subscription_history (
    id INTEGER PRIMARY KEY,
    ipo_id INTEGER NOT NULL REFERENCES ipos(id),
    retail REAL, nii REAL, qib REAL, employee REAL, other REAL, total REAL,
    source TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    source_updated_at TEXT,
    UNIQUE(ipo_id, source, source_updated_at)
);
CREATE TABLE IF NOT EXISTS news_articles (
    id INTEGER PRIMARY KEY,
    ipo_id INTEGER REFERENCES ipos(id),
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    published_at TEXT,
    source TEXT NOT NULL,
    content TEXT,
    snippet TEXT,
    discovered_at TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS sentiment_analysis (
    id INTEGER PRIMARY KEY,
    ipo_id INTEGER NOT NULL REFERENCES ipos(id),
    article_hash TEXT,
    sentiment TEXT NOT NULL,
    sentiment_score INTEGER,
    positives TEXT NOT NULL,
    risks TEXT NOT NULL,
    summary TEXT,
    model TEXT,
    analyzed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY,
    ipo_id REFERENCES ipos(id),
    notification_type TEXT NOT NULL,
    scheduled_job TEXT NOT NULL,
    notification_hash TEXT NOT NULL UNIQUE,
    sent_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_history (
    id INTEGER PRIMARY KEY,
    job_type TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    ipos_discovered INTEGER NOT NULL DEFAULT 0,
    ipos_analyzed INTEGER NOT NULL DEFAULT 0,
    llm_calls INTEGER NOT NULL DEFAULT 0,
    notifications_sent INTEGER NOT NULL DEFAULT 0,
    errors TEXT,
    duration_seconds REAL
);
CREATE TABLE IF NOT EXISTS api_usage (
    id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL,
    request_date TEXT NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0,
    last_request_at TEXT,
    UNIQUE(provider, request_date)
);
"""

# Additive column migrations for older databases.
_MIGRATIONS = [
    "ALTER TABLE ipos ADD COLUMN slug TEXT",
    "ALTER TABLE ipos ADD COLUMN allotment_date TEXT",
    "ALTER TABLE gmp_history ADD COLUMN estimated_listing_price REAL",
]


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            _apply_migrations(connection)


def _apply_migrations(connection: sqlite3.Connection) -> None:
    """Apply additive column migrations; ignore 'duplicate column' errors."""
    for sql in _MIGRATIONS:
        try:
            connection.execute(sql)
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if "duplicate column" in message:
                continue
            raise
    _ensure_unique_index(
        connection,
        "gmp_history",
        "uq_gmp_ipo_source_updated",
        "(ipo_id, source, source_updated_at)",
    )
    _ensure_unique_index(
        connection,
        "subscription_history",
        "uq_sub_ipo_source_updated",
        "(ipo_id, source, source_updated_at)",
    )


def _ensure_unique_index(
    connection: sqlite3.Connection,
    table: str,
    index_name: str,
    columns: str,
) -> None:
    """Create a named UNIQUE index if it does not already exist."""
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,)
    ).fetchone()
    if row is not None:
        return
    try:
        connection.execute(f"CREATE UNIQUE INDEX {index_name} ON {table} {columns}")
    except sqlite3.OperationalError as exc:
        message = str(exc).lower()
        if "already exists" in message or "unique" in message:
            return
        raise