"""Small repository layer; provider code never writes SQL directly."""

from __future__ import annotations

from datetime import datetime
from sqlite3 import Connection

from app.models.ipo import Ipo


class IpoRepository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def upsert(self, ipo: Ipo, now: datetime) -> int:
        values = {
            **ipo.model_dump(exclude={"id", "created_at", "updated_at"}),
            "open_date": _date(ipo.open_date), "close_date": _date(ipo.close_date),
            "listing_date": _date(ipo.listing_date), "created_at": now.isoformat(), "updated_at": now.isoformat(),
        }
        cursor = self.connection.execute(
            """INSERT INTO ipos (external_id, company_name, symbol, ipo_type, exchange, open_date, close_date,
            listing_date, price_low, price_high, lot_size, issue_size, status, created_at, updated_at)
            VALUES (:external_id, :company_name, :symbol, :ipo_type, :exchange, :open_date, :close_date,
            :listing_date, :price_low, :price_high, :lot_size, :issue_size, :status, :created_at, :updated_at)
            ON CONFLICT(external_id) DO UPDATE SET company_name=excluded.company_name, symbol=excluded.symbol,
            ipo_type=excluded.ipo_type, exchange=excluded.exchange, open_date=excluded.open_date,
            close_date=excluded.close_date, listing_date=excluded.listing_date, price_low=excluded.price_low,
            price_high=excluded.price_high, lot_size=excluded.lot_size, issue_size=excluded.issue_size,
            status=excluded.status, updated_at=excluded.updated_at""",
            values,
        )
        if cursor.lastrowid:
            return int(cursor.lastrowid)
        row = self.connection.execute("SELECT id FROM ipos WHERE external_id = ?", (ipo.external_id,)).fetchone()
        assert row is not None
        return int(row["id"])

    def list_all(self) -> list[Ipo]:
        return [Ipo.model_validate(dict(row)) for row in self.connection.execute("SELECT * FROM ipos ORDER BY open_date")]


class RunRepository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def start(self, job_type: str, started_at: datetime) -> int:
        cursor = self.connection.execute(
            "INSERT INTO run_history (job_type, started_at, status) VALUES (?, ?, 'running')",
            (job_type, started_at.isoformat()),
        )
        return int(cursor.lastrowid)

    def finish(self, run_id: int, completed_at: datetime, status: str, errors: str | None = None) -> None:
        self.connection.execute(
            "UPDATE run_history SET completed_at=?, status=?, errors=?, duration_seconds=(julianday(?) - julianday(started_at))*86400 WHERE id=?",
            (completed_at.isoformat(), status, errors, completed_at.isoformat(), run_id),
        )


def _date(value: object) -> str | None:
    return value.isoformat() if value is not None else None  # type: ignore[union-attr]

