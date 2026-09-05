from __future__ import annotations

import logging
from datetime import datetime

from app.config import Settings
from app.database import Database, RunRepository

logger = logging.getLogger(__name__)


def run_foundation_job(settings: Settings, job_type: str) -> None:
    """Record a successful no-op batch run until later phases add providers."""
    database = Database(settings.database_path)
    database.initialize()
    now = datetime.now(settings.timezone)
    with database.connect() as connection:
        runs = RunRepository(connection)
        run_id = runs.start(job_type, now)
        runs.finish(run_id, datetime.now(settings.timezone), "completed")
    logger.info("Completed %s foundation job", job_type)

