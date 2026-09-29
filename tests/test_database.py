from datetime import datetime
from zoneinfo import ZoneInfo

from app.database import Database, GmpRepository, IpoRepository, RunRepository, SubscriptionRepository
from app.models import GmpObservation, Ipo, IpoStatus, SubscriptionObservation


def test_schema_and_repositories(tmp_path) -> None:
    db = Database(tmp_path / "radar.db")
    db.initialize()
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    with db.connect() as connection:
        ipos = IpoRepository(connection)
        first_id = ipos.upsert(Ipo(external_id="demo-1", company_name="Demo Ltd", status=IpoStatus.UPCOMING), now)
        same_id = ipos.upsert(Ipo(external_id="demo-1", company_name="Updated Demo Ltd"), now)
        assert first_id == same_id
        assert ipos.list_all()[0].company_name == "Updated Demo Ltd"
        runs = RunRepository(connection)
        run_id = runs.start("daily", now)
        runs.finish(run_id, now, "completed")
        assert connection.execute("SELECT status FROM run_history WHERE id=?", (run_id,)).fetchone()[0] == "completed"


def test_history_idempotency_uses_collection_date(tmp_path) -> None:
    """Same source timestamp can be collected on different days, once per day."""
    db = Database(tmp_path / "history.db")
    db.initialize()
    with db.connect() as connection:
        ipo_id = IpoRepository(connection).upsert(
            Ipo(external_id="history-1", company_name="History IPO"), datetime.now(ZoneInfo("UTC"))
        )
        gmp = GmpRepository(connection)
        sub = SubscriptionRepository(connection)
        source_time = datetime(2026, 9, 25, tzinfo=ZoneInfo("UTC"))
        first = GmpObservation(
            ipo_id=ipo_id, gmp=15.5, source="ipoguru", retrieved_at=datetime(2026, 9, 26, 2, tzinfo=ZoneInfo("UTC")), source_updated_at=source_time
        )
        second = first.model_copy(update={"gmp": 16.0, "retrieved_at": datetime(2026, 9, 27, 2, tzinfo=ZoneInfo("UTC"))})
        assert gmp.insert(first) is True
        assert gmp.insert(second) is True
        assert gmp.insert(first) is False
        assert connection.execute("SELECT COUNT(*) FROM gmp_history WHERE ipo_id=?", (ipo_id,)).fetchone()[0] == 2

        sub_first = SubscriptionObservation(
            ipo_id=ipo_id, qib=0.0, nii=None, retail=1.0, total=0.5, source="ipoguru",
            retrieved_at=datetime(2026, 9, 26, 2, tzinfo=ZoneInfo("UTC")), source_updated_at=source_time
        )
        sub_second = sub_first.model_copy(update={"total": 0.8, "retrieved_at": datetime(2026, 9, 27, 2, tzinfo=ZoneInfo("UTC"))})
        assert sub.insert(sub_first) is True
        assert sub.insert(sub_second) is True
        assert sub.insert(sub_first) is False
        assert connection.execute("SELECT COUNT(*) FROM subscription_history WHERE ipo_id=?", (ipo_id,)).fetchone()[0] == 2

