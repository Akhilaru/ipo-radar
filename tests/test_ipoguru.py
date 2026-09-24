"""Tests for IPO Guru provider."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.config import Settings
from app.database import ApiUsageRepository, Database
from app.sources.ipoguru import (
    IpoGuruAuthError,
    IpoGuruClient,
    IpoGuruError,
    IpoGuruRateLimitError,
    IpoGuruRateLimiter,
    IpoGuruResponseError,
    _parse_float,
    _parse_gmp,
    _parse_ipo,
    _parse_price_band,
    _parse_subscription,
)


@pytest.fixture
def settings():
    return Settings(
        timezone=timezone.utc,
        database_path=None,
        ipoguru_api_key="test_key",
        ipoguru_daily_limit=10,
        ipoguru_min_request_interval_seconds=60,
        telegram_bot_token=None,
        telegram_chat_id=None,
        openrouter_api_key=None,
        openrouter_model=None,
        log_level="INFO",
    )


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.initialize()
    return database


@pytest.fixture
def usage_repo(db):
    with db.connect() as conn:
        yield ApiUsageRepository(conn)


# --- Parsing tests ---


def test_parse_ipo_basic():
    data = {
        "slug": "test-ipo",
        "name": "Test IPO Ltd",
        "type": "mainboard",
        "status": "open",
        "price_band": "100-200",
        "lot_size": 50,
        "issue_size": 1000000,
    }
    ipo = _parse_ipo(data)
    assert ipo.external_id == "ipoguru:test-ipo"
    assert ipo.slug == "test-ipo"
    assert ipo.company_name == "Test IPO Ltd"
    assert ipo.status.value == "open"
    assert ipo.price_low == 100.0
    assert ipo.price_high == 200.0
    assert ipo.lot_size == 50


def test_parse_ipo_sme():
    data = {"slug": "sme-ipo", "name": "SME IPO", "type": "sme", "status": "open"}
    ipo = _parse_ipo(data)
    assert ipo.ipo_type.value == "sme"


def test_parse_ipo_missing_name():
    data = {"slug": "no-name", "type": "mainboard", "status": "open"}
    ipo = _parse_ipo(data)
    assert ipo.company_name == "no-name"


def test_parse_price_band_variations():
    assert _parse_price_band("100-200") == (100.0, 200.0)
    assert _parse_price_band("₹100 - ₹200") == (100.0, 200.0)
    assert _parse_price_band("150") == (150.0, 150.0)
    assert _parse_price_band(None) == (None, None)
    assert _parse_price_band(100) == (100.0, 100.0)


def test_parse_float_variations():
    assert _parse_float("100") == 100.0
    assert _parse_float("100.5") == 100.5
    assert _parse_float("₹1,000") == 1000.0
    assert _parse_float(None) is None
    assert _parse_float("") is None


# --- GMP tests ---


def test_parse_gmp_present():
    data = {
        "price": "8",
        "percentage": "4.32",
        "estimated_listing_price": 193,
        "updated_at": "2026-09-23T05:54:06.000000Z",
    }
    retrieved = datetime(2026, 9, 23, 6, 0, 0, tzinfo=timezone.utc)
    gmp = _parse_gmp(data, retrieved)
    assert gmp is not None
    assert gmp.gmp == 8.0
    assert gmp.gmp_percentage == 4.32
    assert gmp.estimated_listing_price == 193.0
    assert gmp.source == "ipoguru"
    assert gmp.source_updated_at is not None


def test_parse_gmp_zero():
    data = {"price": "0", "percentage": "0", "updated_at": "2026-09-23T05:54:06Z"}
    retrieved = datetime(2026, 9, 23, 6, 0, 0, tzinfo=timezone.utc)
    gmp = _parse_gmp(data, retrieved)
    assert gmp is not None
    assert gmp.gmp == 0.0


def test_parse_gmp_missing():
    data = {}
    retrieved = datetime(2026, 9, 23, 6, 0, 0, tzinfo=timezone.utc)
    gmp = _parse_gmp(data, retrieved)
    assert gmp is None


def test_parse_gmp_null_price():
    data = {"price": None, "percentage": "4.32"}
    retrieved = datetime(2026, 9, 23, 6, 0, 0, tzinfo=timezone.utc)
    gmp = _parse_gmp(data, retrieved)
    assert gmp is None


def test_parse_gmp_missing_updated_at_uses_fallback():
    data = {"price": "10"}
    retrieved = datetime(2026, 9, 23, 6, 30, 0, tzinfo=timezone.utc)
    gmp = _parse_gmp(data, retrieved)
    assert gmp is not None
    assert gmp.source_updated_at == datetime(2026, 9, 23, 0, 0, 0, tzinfo=timezone.utc)


# --- Subscription tests ---


def test_parse_subscription_all_present():
    data = {
        "qib": 10.5,
        "nii": 15.2,
        "retail": 20.1,
        "total": 45.8,
        "updated_at": "2026-09-23T05:54:06Z",
    }
    retrieved = datetime(2026, 9, 23, 6, 0, 0, tzinfo=timezone.utc)
    sub = _parse_subscription(data, retrieved)
    assert sub is not None
    assert sub.qib == 10.5
    assert sub.nii == 15.2
    assert sub.retail == 20.1
    assert sub.total == 45.8
    assert sub.source == "ipoguru"


def test_parse_subscription_some_null():
    data = {"qib": 10.5, "nii": None, "retail": 20.1, "total": 30.6}
    retrieved = datetime(2026, 9, 23, 6, 0, 0, tzinfo=timezone.utc)
    sub = _parse_subscription(data, retrieved)
    assert sub is not None
    assert sub.qib == 10.5
    assert sub.nii is None
    assert sub.retail == 20.1


def test_parse_subscription_all_null():
    data = {"qib": None, "nii": None, "retail": None, "total": None}
    retrieved = datetime(2026, 9, 23, 6, 0, 0, tzinfo=timezone.utc)
    sub = _parse_subscription(data, retrieved)
    assert sub is None


def test_parse_subscription_missing_timestamp():
    data = {"qib": 10.5, "total": 10.5}
    retrieved = datetime(2026, 9, 23, 6, 30, 0, tzinfo=timezone.utc)
    sub = _parse_subscription(data, retrieved)
    assert sub is not None
    assert sub.source_updated_at == datetime(2026, 9, 23, 0, 0, 0, tzinfo=timezone.utc)



# --- Rate limiter tests ---


def test_rate_limiter_prevents_rapid_requests(usage_repo):
    limiter = IpoGuruRateLimiter(usage_repo, daily_limit=10, min_interval_seconds=60)
    limiter.record()
    with pytest.raises(IpoGuruRateLimitError, match="minimum interval"):
        limiter.check()


def test_rate_limiter_enforces_daily_limit(usage_repo):
    limiter = IpoGuruRateLimiter(usage_repo, daily_limit=2, min_interval_seconds=0)
    limiter.record()
    limiter.record()
    with pytest.raises(IpoGuruRateLimitError, match="daily limit"):
        limiter.check()


def test_rate_limiter_respects_existing_usage(usage_repo):
    limiter = IpoGuruRateLimiter(usage_repo, daily_limit=10, min_interval_seconds=60)
    count = limiter.record()
    assert count == 1


def test_rate_limiter_allows_after_interval(usage_repo):
    from datetime import timedelta
    past = datetime.now(timezone.utc) - timedelta(seconds=120)
    limiter = IpoGuruRateLimiter(
        usage_repo, daily_limit=10, min_interval_seconds=60, now=past
    )
    limiter.record()
    limiter2 = IpoGuruRateLimiter(usage_repo, daily_limit=10, min_interval_seconds=60)
    limiter2.check()  # Should not raise


# --- Client helpers ---


def _mock_http(status_code=200, json_data=None, headers=None, side_effect=None):
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.headers = headers or {}
    if json_data is not None:
        mock_response.json.return_value = json_data
    elif side_effect is not None:
        mock_response.json.side_effect = side_effect
    mock_http = AsyncMock()
    if isinstance(side_effect, Exception):
        mock_http.get.side_effect = side_effect
    else:
        mock_http.get.return_value = mock_response
    return mock_http


SAMPLE_SUCCESS_RESPONSE = {
    "success": True,
    "plan": "free",
    "count": 2,
    "data": [
        {
            "slug": "ipo-1",
            "name": "IPO One",
            "type": "mainboard",
            "status": "open",
            "price_band": "100-200",
            "gmp": {
                "price": "10",
                "percentage": "5",
                "estimated_listing_price": 210,
                "updated_at": "2026-09-23T05:00:00Z",
            },
            "subscription": {
                "qib": 10, "nii": 15, "retail": 20, "total": 45,
                "updated_at": "2026-09-23T05:00:00Z",
            },
        },
        {"slug": "ipo-2", "name": "IPO Two", "type": "sme", "status": "open"},
    ],
}



@pytest.mark.asyncio
async def test_client_success_response(settings, usage_repo):
    mock_http = _mock_http(200, SAMPLE_SUCCESS_RESPONSE)
    async with IpoGuruClient(settings, usage_repo, http_client=mock_http) as client:
        result = await client.fetch_open_ipos()
    assert len(result.ipo_data) == 2
    assert result.ipo_data[0].ipo.slug == "ipo-1"
    assert result.ipo_data[0].gmp is not None
    assert result.ipo_data[0].gmp.gmp == 10.0
    assert result.ipo_data[0].subscription is not None
    assert result.ipo_data[0].subscription.qib == 10
    assert result.ipo_data[1].ipo.slug == "ipo-2"
    assert result.ipo_data[1].gmp is None
    assert result.ipo_data[1].subscription is None
    assert result.requests_used_today == 1
    assert result.daily_limit == 10


@pytest.mark.asyncio
async def test_client_401_error(settings, usage_repo):
    mock_http = _mock_http(401)
    async with IpoGuruClient(settings, usage_repo, http_client=mock_http) as client:
        with pytest.raises(IpoGuruAuthError):
            await client.fetch_open_ipos()


@pytest.mark.asyncio
async def test_client_403_error(settings, usage_repo):
    mock_http = _mock_http(403)
    async with IpoGuruClient(settings, usage_repo, http_client=mock_http) as client:
        with pytest.raises(IpoGuruAuthError):
            await client.fetch_open_ipos()


@pytest.mark.asyncio
async def test_client_429_error(settings, usage_repo):
    mock_http = _mock_http(429, headers={"Retry-After": "60"})
    async with IpoGuruClient(settings, usage_repo, http_client=mock_http) as client:
        with pytest.raises(IpoGuruRateLimitError, match="retry after"):
            await client.fetch_open_ipos()


@pytest.mark.asyncio
async def test_client_timeout(settings, usage_repo):
    mock_http = AsyncMock()
    mock_http.get.side_effect = httpx.TimeoutException("timeout")
    async with IpoGuruClient(settings, usage_repo, http_client=mock_http) as client:
        with pytest.raises(IpoGuruError, match="timed out"):
            await client.fetch_open_ipos()


@pytest.mark.asyncio
async def test_client_malformed_json(settings, usage_repo):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.json.side_effect = Exception("invalid json")
    mock_http = AsyncMock()
    mock_http.get.return_value = mock_response
    async with IpoGuruClient(settings, usage_repo, http_client=mock_http) as client:
        with pytest.raises(IpoGuruResponseError, match="malformed"):
            await client.fetch_open_ipos()


@pytest.mark.asyncio
async def test_client_success_false(settings, usage_repo):
    mock_http = _mock_http(200, {"success": False})
    async with IpoGuruClient(settings, usage_repo, http_client=mock_http) as client:
        with pytest.raises(IpoGuruResponseError, match="failure"):
            await client.fetch_open_ipos()


@pytest.mark.asyncio
async def test_client_missing_data(settings, usage_repo):
    mock_http = _mock_http(200, {"success": True})
    async with IpoGuruClient(settings, usage_repo, http_client=mock_http) as client:
        with pytest.raises(IpoGuruResponseError, match="missing"):
            await client.fetch_open_ipos()


@pytest.mark.asyncio
async def test_client_no_api_key_raises(usage_repo):
    bad_settings = Settings(
        timezone=timezone.utc, database_path=None,
        ipoguru_api_key=None, ipoguru_daily_limit=10,
        ipoguru_min_request_interval_seconds=60,
        telegram_bot_token=None, telegram_chat_id=None,
        openrouter_api_key=None, openrouter_model=None, log_level="INFO",
    )
    with pytest.raises(IpoGuruError, match="not configured"):
        IpoGuruClient(bad_settings, usage_repo)



# --- Idempotency test ---


@pytest.mark.asyncio
async def test_idempotency_same_response_twice(settings, db):
    """Identical responses should not create duplicate observations."""
    mock_http = _mock_http(200, {
        "success": True,
        "data": [{
            "slug": "test-ipo",
            "name": "Test IPO",
            "type": "mainboard",
            "status": "open",
            "gmp": {"price": "10", "updated_at": "2026-09-23T05:00:00Z"},
            "subscription": {
                "qib": 10, "nii": 15, "retail": 20, "total": 45,
                "updated_at": "2026-09-23T05:00:00Z",
            },
        }],
    })

    from app.database import GmpRepository, IpoRepository, SubscriptionRepository

    async def _run_fetch():
        with db.connect() as conn:
            usage_repo = ApiUsageRepository(conn)
            async with IpoGuruClient(settings, usage_repo, http_client=mock_http) as client:
                result = await client.fetch_open_ipos()
            ipos_repo = IpoRepository(conn)
            gmp_repo = GmpRepository(conn)
            sub_repo = SubscriptionRepository(conn)
            for ipo_data in result.ipo_data:
                ipo_id = ipos_repo.upsert(ipo_data.ipo, datetime.now(timezone.utc))
                if ipo_data.gmp:
                    ipo_data.gmp.ipo_id = ipo_id
                    gmp_repo.insert(ipo_data.gmp)
                if ipo_data.subscription:
                    ipo_data.subscription.ipo_id = ipo_id
                    sub_repo.insert(ipo_data.subscription)

    await _run_fetch()
    # Reset usage to allow second fetch (simulating new day or cleared counter)
    with db.connect() as conn:
        conn.execute("DELETE FROM api_usage")
    await _run_fetch()

    with db.connect() as conn:
        gmp_count = conn.execute("SELECT COUNT(*) FROM gmp_history").fetchone()[0]
        sub_count = conn.execute("SELECT COUNT(*) FROM subscription_history").fetchone()[0]
        ipo_count = conn.execute("SELECT COUNT(*) FROM ipos").fetchone()[0]
    assert ipo_count == 1
    assert gmp_count == 1
    assert sub_count == 1

    assert _parse_float(100) == 100.0
