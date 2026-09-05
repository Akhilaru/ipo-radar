from app.config import Settings
from app.jobs.common import run_foundation_job


def run(settings: Settings) -> None:
    run_foundation_job(settings, "daily")

