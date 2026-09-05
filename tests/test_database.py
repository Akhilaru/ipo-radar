from datetime import datetime
from zoneinfo import ZoneInfo

from app.database import Database, IpoRepository, RunRepository
from app.models import Ipo, IpoStatus


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

