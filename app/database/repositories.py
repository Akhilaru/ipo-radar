"""Small repository layer; provider code never writes SQL directly."""

from __future__ import annotations

from datetime import date, datetime
from sqlite3 import Connection, IntegrityError

from app.models.gmp import GmpObservation
from app.models.ipo import Ipo
from app.models.subscription import SubscriptionObservation


class IpoRepository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def upsert(self, ipo: Ipo, now: datetime) -> int:
        values = {
            **ipo.model_dump(exclude={"id", "created_at", "updated_at"}),
            "open_date": _date(ipo.open_date),
            "close_date": _date(ipo.close_date),
            "allotment_date": _date(ipo.allotment_date),
            "listing_date": _date(ipo.listing_date),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        cursor = self.connection.execute(
            """INSERT INTO ipos (external_id, slug, company_name, symbol, ipo_type, exchange,
            open_date, close_date, allotment_date, listing_date, price_low, price_high,
            lot_size, issue_size, status, created_at, updated_at)
            VALUES (:external_id, :slug, :company_name, :symbol, :ipo_type, :exchange,
            :open_date, :close_date, :allotment_date, :listing_date, :price_low, :price_high,
            :lot_size, :issue_size, :status, :created_at, :updated_at)
            ON CONFLICT(external_id) DO UPDATE SET
            slug=COALESCE(excluded.slug, ipos.slug),
            company_name=excluded.company_name,
            symbol=COALESCE(excluded.symbol, ipos.symbol),
            ipo_type=excluded.ipo_type,
            exchange=COALESCE(excluded.exchange, ipos.exchange),
            open_date=COALESCE(excluded.open_date, ipos.open_date),
            close_date=COALESCE(excluded.close_date, ipos.close_date),
            allotment_date=COALESCE(excluded.allotment_date, ipos.allotment_date),
            listing_date=COALESCE(excluded.listing_date, ipos.listing_date),
            price_low=COALESCE(excluded.price_low, ipos.price_low),
            price_high=COALESCE(excluded.price_high, ipos.price_high),
            lot_size=COALESCE(excluded.lot_size, ipos.lot_size),
            issue_size=COALESCE(excluded.issue_size, ipos.issue_size),
            status=excluded.status,
            updated_at=excluded.updated_at""",
            values,
        )
        if cursor.lastrowid:
            return int(cursor.lastrowid)
        row = self.connection.execute(
            "SELECT id FROM ipos WHERE external_id = ?", (ipo.external_id,)
        ).fetchone()
        assert row is not None
        return int(row["id"])

    def list_all(self) -> list[Ipo]:
        return [
            Ipo.model_validate(dict(row))
            for row in self.connection.execute("SELECT * FROM ipos ORDER BY open_date")
        ]



class GmpRepository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def insert(self, observation: GmpObservation) -> bool:
        """Insert a GMP observation; return False if a duplicate is skipped."""
        try:
            self.connection.execute(
                """INSERT INTO gmp_history
                (ipo_id, gmp, gmp_percentage, estimated_listing_price,
                 source, retrieved_at, source_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    observation.ipo_id,
                    observation.gmp,
                    observation.gmp_percentage,
                    observation.estimated_listing_price,
                    observation.source,
                    observation.retrieved_at.isoformat(),
                    observation.source_updated_at.isoformat() if observation.source_updated_at else None,
                ),
            )
            return True
        except IntegrityError:
            return False

    def count_for_ipo(self, ipo_id: int) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM gmp_history WHERE ipo_id = ?", (ipo_id,)
        ).fetchone()
        return int(row[0])


class SubscriptionRepository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def insert(self, observation: SubscriptionObservation) -> bool:
        """Insert a subscription observation; return False if a duplicate is skipped."""
        try:
            self.connection.execute(
                """INSERT INTO subscription_history
                (ipo_id, retail, nii, qib, employee, other, total,
                 source, retrieved_at, source_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    observation.ipo_id,
                    observation.retail,
                    observation.nii,
                    observation.qib,
                    observation.employee,
                    observation.other,
                    observation.total,
                    observation.source,
                    observation.retrieved_at.isoformat(),
                    observation.source_updated_at.isoformat() if observation.source_updated_at else None,
                ),
            )
            return True
        except IntegrityError:
            return False

    def count_for_ipo(self, ipo_id: int) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM subscription_history WHERE ipo_id = ?", (ipo_id,)
        ).fetchone()
        return int(row[0])


class ApiUsageRepository:
    """Tracks per-provider daily API usage for quota enforcement."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def get_usage(self, provider: str, request_date: date) -> tuple[int, datetime | None]:
        """Return (request_count, last_request_at) for the given provider+date."""
        row = self.connection.execute(
            "SELECT request_count, last_request_at FROM api_usage WHERE provider=? AND request_date=?",
            (provider, request_date.isoformat()),
        ).fetchone()
        if row is None:
            return 0, None
        last_at = None
        if row["last_request_at"]:
            last_at = datetime.fromisoformat(row["last_request_at"])
        return int(row["request_count"]), last_at

    def record(self, provider: str, request_date: date, request_at: datetime) -> int:
        """Increment the daily counter and return the new count."""
        self.connection.execute(
            """INSERT INTO api_usage (provider, request_date, request_count, last_request_at)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(provider, request_date) DO UPDATE SET
            request_count = request_count + 1,
            last_request_at = excluded.last_request_at""",
            (provider, request_date.isoformat(), request_at.isoformat()),
        )
        row = self.connection.execute(
            "SELECT request_count FROM api_usage WHERE provider=? AND request_date=?",
            (provider, request_date.isoformat()),
        ).fetchone()
        return int(row["request_count"])


class RunRepository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def start(self, job_type: str, started_at: datetime) -> int:
        cursor = self.connection.execute(
            "INSERT INTO run_history (job_type, started_at, status) VALUES (?, ?, 'running')",
            (job_type, started_at.isoformat()),
        )
        return int(cursor.lastrowid)

    def finish(
        self,
        run_id: int,
        completed_at: datetime,
        status: str,
        errors: str | None = None,
        ipos_discovered: int = 0,
        ipos_analyzed: int = 0,
        notifications_sent: int = 0,
    ) -> None:
        self.connection.execute(
            """UPDATE run_history
            SET completed_at=?, status=?, errors=?,
            ipos_discovered=?, ipos_analyzed=?, notifications_sent=?,
            duration_seconds=(julianday(?) - julianday(started_at))*86400
            WHERE id=?""",
            (
                completed_at.isoformat(),
                status,
                errors,
                ipos_discovered,
                ipos_analyzed,
                notifications_sent,
                completed_at.isoformat(),
                run_id,
            ),
        )


def _date(value: object) -> str | None:
    return value.isoformat() if value is not None else None  # type: ignore[union-attr]