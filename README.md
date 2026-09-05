# IPO Radar 🇮🇳

A lightweight, short-lived batch job for tracking Indian IPOs. It is a personal research aid, not financial advice; future scores and GMP information will never be presented as a guarantee of listing performance.

## Phase 1 status

This foundation provides typed internal models, environment configuration, SQLite persistence, run history, a batch-job CLI, structured logging, Docker support, and tests. It deliberately includes no live data source, Telegram, OpenRouter, news, GMP/subscription analysis, or scoring implementation yet.

The provider contract in `app/sources/base.py` is intentionally present now so Phase 2's IPO Guru adapter can remain isolated from the rest of the application.

## Setup

Copy `.env.example` to `.env`, then adjust the database path if needed. Python 3.12+ is required.

```bash
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m app --job daily
python -m app --job last-day-10am
python -m app --job last-day-1pm
python -m pytest
```

Jobs initialize `/app/data/ipo_radar.db` in Docker (or `data/ipo_radar.db` locally by default), record their run, and exit.

## Docker

```bash
docker compose run --rm ipo-radar python -m app --job daily
docker compose run --rm ipo-radar python -m app --job last-day-10am
docker compose run --rm ipo-radar python -m app --job last-day-1pm
```

The `data` directory is mounted from the host. Schedule these commands with the host operating system; this repository intentionally does not include a permanent scheduler or service.

## Architecture

- `app/models`: normalized Pydantic models independent of external providers.
- `app/database`: SQLite schema and repository layer.
- `app/jobs`: short-lived job entry points.
- `app/sources`, `app/analysis`, and `app/notifications`: intentionally deferred to later phases.
