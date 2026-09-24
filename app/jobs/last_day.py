"""Last-day jobs for IPOs closing today.

These jobs are structured to support future Telegram notifications.
For now, they record a successful run without sending notifications.
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.config import Settings
from app.database import Database, RunRepository

logger = logging.getLogger(__name__)


def run(settings: Settings, hour: str) -> None:
    """Run the last-day job for the specified hour (10am or 1pm).
    
    Future implementation will:
    1. Identify IPOs whose closing date is today
    2. Refresh the latest IPO Guru data (respecting rate limits)
    3. Produce data required for Telegram alerts
    
    For now, this is a no-op that records a successful run.
    """
    database = Database(settings.database_path)
    database.initialize()
    now = datetime.now(settings.timezone)
    
    with database.connect() as connection:
        runs = RunRepository(connection)
        run_id = runs.start(f"last-day-{hour}", now)
        
        # TODO: Implement IPO closing detection and data refresh
        # TODO: Implement Telegram notification (when enabled)
        
        runs.finish(run_id, datetime.now(settings.timezone), "completed")
    
    logger.info("Completed last-day-%s job (no-op)", hour)


