from __future__ import annotations

import argparse

from app.config import Settings
from app.jobs import analyze, daily, last_day
from app.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a short-lived IPO Radar job.")
    parser.add_argument(
        "--job",
        required=True,
        choices=("daily", "last-day-10am", "last-day-1pm", "analyze"),
    )
    args = parser.parse_args()
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    if args.job == "daily":
        daily.run(settings)
    elif args.job == "last-day-10am":
        last_day.run(settings, "10am")
    elif args.job == "last-day-1pm":
        last_day.run(settings, "1pm")
    elif args.job == "analyze":
        analyze.run(settings)


if __name__ == "__main__":
    main()

