"""Daily ingestion job – primary source: IPO Guru."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.config import Settings
from app.database import (
    ApiUsageRepository,
    Database,
    GmpRepository,
    IpoRepository,
    RunRepository,
    SubscriptionRepository,
)
from app.sources.ipoguru import (
    IpoGuruClient,
    IpoGuruError,
    IpoGuruRateLimitError,
    _parse_gmp,
    _parse_subscription,
)

logger = logging.getLogger(__name__)


def run(settings: Settings) -> None:
    asyncio.run(_run_async(settings))


async def _run_async(settings: Settings) -> None:
    database = Database(settings.database_path)
    database.initialize()
    now = datetime.now(settings.timezone)

    with database.connect() as connection:
        runs = RunRepository(connection)
        run_id = runs.start("daily", now)

        ipos_discovered = 0
        gmp_stored = 0
        sub_stored = 0
        errors: list[str] = []
        status = "completed"

        try:
            usage_repo = ApiUsageRepository(connection)
            ipos_repo = IpoRepository(connection)
            gmp_repo = GmpRepository(connection)
            sub_repo = SubscriptionRepository(connection)

            async with IpoGuruClient(settings, usage_repo) as client:
                result = await client.fetch_open_ipos()

            logger.info(
                "IPO Guru: %d open IPOs, %d GMP observations, "
                "%d subscription observations (requests %d/%d)",
                len(result.ipos),
                len(result.gmp_observations),
                len(result.subscription_observations),
                result.requests_used_today,
                result.daily_limit,
            )

            # Process each IPO with its GMP and subscription data
            for ipo_data in result.ipo_data:
                ipo = ipo_data.ipo
                ipo_id = ipos_repo.upsert(ipo, datetime.now(timezone.utc))
                ipos_discovered += 1

                if ipo_data.gmp is not None:
                    ipo_data.gmp.ipo_id = ipo_id
                    if gmp_repo.insert(ipo_data.gmp):
                        gmp_stored += 1

                if ipo_data.subscription is not None:
                    ipo_data.subscription.ipo_id = ipo_id
                    if sub_repo.insert(ipo_data.subscription):
                        sub_stored += 1

            logger.info(
                "Persisted: %d IPOs upserted, %d GMP stored, %d subscriptions stored",
                ipos_discovered,
                gmp_stored,
                sub_stored,
            )

        except IpoGuruRateLimitError as exc:
            logger.warning("IPO Guru rate limit: %s", exc)
            errors.append(f"rate_limit:{exc}")
            status = "rate_limited"
        except IpoGuruError as exc:
            logger.error("IPO Guru error: %s", exc)
            errors.append(str(exc))
            status = "failed"
        except Exception as exc:  # pragma: no cover - safety net
            logger.exception("Unexpected error in daily job")
            errors.append(f"unexpected:{exc}")
            status = "failed"

        completed_at = datetime.now(settings.timezone)
        runs.finish(
            run_id,
            completed_at,
            status,
            errors="; ".join(errors) if errors else None,
            ipos_discovered=ipos_discovered,
        )



