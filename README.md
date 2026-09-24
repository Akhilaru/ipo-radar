# IPO Radar 🇮🇳

A lightweight, short-lived batch job for tracking Indian IPOs. It is a personal research aid, not financial advice; future scores and GMP information will never be presented as a guarantee of listing performance.

## Phase 2 status

IPO Guru is now the primary data source for open IPOs, GMP (Grey Market Premium), and subscription data. The system enforces strict rate limits (10 requests/day, 1 request/minute) and builds historical observations without creating duplicates.

IPOAlerts and NSE providers remain available as fallback options but are not called during normal daily ingestion.

## Setup

Copy `.env.example` to `.env` and configure the required environment variables:

```bash
IPOGURU_API_KEY=your_api_key_here
IPOGURU_DAILY_LIMIT=10
IPOGURU_MIN_REQUEST_INTERVAL_SECONDS=60
```

Python 3.12+ is required.

```bash
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m app --job daily
python -m app --job last-day-10am
python -m app --job last-day-1pm
python -m pytest
```

Jobs initialize `data/ipo_radar.db` locally (or `/app/data/ipo_radar.db` in Docker), record their run, and exit.

## Docker

```bash
docker compose run --rm ipo-radar python -m app --job daily
docker compose run --rm ipo-radar python -m app --job last-day-10am
docker compose run --rm ipo-radar python -m app --job last-day-1pm
```

The `data` directory is mounted from the host. Schedule these commands with the host operating system; this repository intentionally does not include a permanent scheduler or service.

## Architecture

- `app/models`: normalized Pydantic models independent of external providers.
- `app/database`: SQLite schema and repository layer with deduplication constraints.
- `app/sources`: provider integrations (IPO Guru primary, IPOAlerts/NSE available as fallback).
- `app/jobs`: short-lived job entry points with rate limiting and quota management.
- `app/analysis` and `app/notifications`: intentionally deferred to later phases.

## Data Flow

```
IPO Guru API (1 request/day)
    ↓
Open IPOs with GMP + Subscription
    ↓
Parse & normalize
    ↓
SQLite (ipos, gmp_history, subscription_history)
    ↓
Historical observations (no duplicates)
```

## Rate Limiting

The system enforces IPO Guru's actual free-tier limits:
- **10 requests per day** (persisted across restarts)
- **60 seconds minimum between requests**
- **HTTP 429 handling** with retry-after respect
- **No automatic retries** on quota exhaustion

## Deduplication

GMP and subscription observations use database uniqueness constraints:
- `UNIQUE(ipo_id, source, source_updated_at)` for both tables
- Identical observations are not duplicated
- Historical changes are preserved (e.g., GMP ₹10 → ₹12 → ₹15 over time)
