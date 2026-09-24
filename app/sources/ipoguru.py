"""IPO Guru provider – primary source for open IPOs, GMP, and subscription data."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import httpx

from app.config import Settings
from app.database import ApiUsageRepository
from app.models.gmp import GmpObservation
from app.models.ipo import Ipo, IpoStatus, IpoType
from app.models.subscription import SubscriptionObservation

logger = logging.getLogger(__name__)

PROVIDER_NAME = "ipoguru"
API_BASE_URL = "https://www.ipoguru.in/api/v1"


# --- Exceptions ---


class IpoGuruError(Exception):
    """Base exception for IPO Guru provider errors."""


class IpoGuruAuthError(IpoGuruError):
    """Authentication failed (401/403)."""


class IpoGuruRateLimitError(IpoGuruError):
    """Rate limit or quota exceeded."""


class IpoGuruResponseError(IpoGuruError):
    """Invalid or malformed API response."""


# --- Parsing helpers ---


def _parse_float(value: Any) -> float | None:
    """Parse a numeric value from various formats."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        cleaned = re.sub(r"[₹$,]", "", cleaned)
        cleaned = cleaned.strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _parse_price_band(value: Any) -> tuple[float | None, float | None]:
    """Parse price band from various formats."""
    if value is None:
        return (None, None)
    if isinstance(value, (int, float)):
        return (float(value), float(value))
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return (None, None)
        cleaned = re.sub(r"[₹$]", "", cleaned)
        if "-" in cleaned:
            parts = cleaned.split("-", 1)
            low = _parse_float(parts[0].strip())
            high = _parse_float(parts[1].strip())
            return (low, high)
        val = _parse_float(cleaned)
        return (val, val)
    return (None, None)


def _parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO 8601 datetime string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            if cleaned.endswith("Z"):
                cleaned = cleaned[:-1] + "+00:00"
            return datetime.fromisoformat(cleaned)
        except ValueError:
            return None
    return None


def _parse_date(value: Any) -> date | None:
    """Parse a date string."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return date.fromisoformat(cleaned[:10])
        except ValueError:
            pass
        dt = _parse_datetime(cleaned)
        if dt:
            return dt.date()
    return None


def _parse_ipo_type(value: Any) -> IpoType:
    """Parse IPO type from API response."""
    if value is None:
        return IpoType.MAINBOARD
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "sme":
            return IpoType.SME
    return IpoType.MAINBOARD


def _parse_status(value: Any) -> IpoStatus:
    """Parse IPO status from API response."""
    if value is None:
        return IpoStatus.UNKNOWN
    if isinstance(value, str):
        normalized = value.strip().lower()
        status_map = {
            "upcoming": IpoStatus.UPCOMING,
            "open": IpoStatus.OPEN,
            "closed": IpoStatus.CLOSED,
            "listed": IpoStatus.LISTED,
        }
        return status_map.get(normalized, IpoStatus.UNKNOWN)
    return IpoStatus.UNKNOWN


def _parse_ipo(data: dict[str, Any]) -> Ipo:
    """Parse IPO metadata from API response."""
    slug = data.get("slug")
    name = data.get("name") or slug or "Unknown IPO"
    
    # Generate external_id: prefer slug, fallback to name-based ID
    if slug:
        external_id = f"{PROVIDER_NAME}:{slug}"
    else:
        # Use name + open_date or a hash to ensure uniqueness
        open_date = data.get("open_date")
        if open_date:
            slug = f"{name.lower().replace(' ', '-')}-{open_date}"
        else:
            # Last resort: use a hash of the name
            import hashlib
            name_hash = hashlib.md5(name.encode()).hexdigest()[:8]
            slug = f"ipo-{name_hash}"
        external_id = f"{PROVIDER_NAME}:{slug}"
    
    ipo_type = _parse_ipo_type(data.get("type"))
    status = _parse_status(data.get("status"))

    price_band = data.get("price_band")
    price_low, price_high = _parse_price_band(price_band)

    if price_low is None and price_high is None:
        issue_price = _parse_float(data.get("issue_price"))
        if issue_price is not None:
            price_low = issue_price
            price_high = issue_price

    open_date = _parse_date(data.get("open_date"))
    close_date = _parse_date(data.get("close_date"))
    allotment_date = _parse_date(data.get("allotment_date"))
    listing_date = _parse_date(data.get("listing_date"))

    lot_size_raw = data.get("lot_size")
    lot_size = int(lot_size_raw) if lot_size_raw is not None else None

    issue_size = _parse_float(data.get("issue_size"))
    exchange = data.get("exchange") or data.get("listing_exchange")

    return Ipo(
        external_id=external_id,
        slug=slug,
        company_name=name,
        symbol=data.get("symbol"),
        ipo_type=ipo_type,
        exchange=exchange,
        open_date=open_date,
        close_date=close_date,
        allotment_date=allotment_date,
        listing_date=listing_date,
        price_low=price_low,
        price_high=price_high,
        lot_size=lot_size,
        issue_size=issue_size,
        status=status,
    )


def _midnight_fallback(retrieved_at: datetime) -> datetime:
    """Return midnight UTC of the retrieved_at date as a fallback timestamp."""
    return retrieved_at.astimezone(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _parse_gmp(data: dict[str, Any], retrieved_at: datetime) -> GmpObservation | None:
    """Parse GMP observation from API response."""
    if not data:
        return None

    gmp_price = _parse_float(data.get("price"))
    if gmp_price is None:
        return None

    gmp_percentage = _parse_float(data.get("percentage"))
    estimated_listing_price = _parse_float(data.get("estimated_listing_price"))

    source_updated_at = _parse_datetime(data.get("updated_at"))
    if source_updated_at is None:
        source_updated_at = _midnight_fallback(retrieved_at)

    return GmpObservation(
        ipo_id=0,
        gmp=gmp_price,
        gmp_percentage=gmp_percentage,
        estimated_listing_price=estimated_listing_price,
        source=PROVIDER_NAME,
        retrieved_at=retrieved_at,
        source_updated_at=source_updated_at,
    )


def _parse_subscription(
    data: dict[str, Any], retrieved_at: datetime
) -> SubscriptionObservation | None:
    """Parse subscription observation from API response."""
    if not data:
        return None

    qib = _parse_float(data.get("qib"))
    nii = _parse_float(data.get("nii"))
    retail = _parse_float(data.get("retail"))
    total = _parse_float(data.get("total"))
    employee = _parse_float(data.get("employee"))
    other = _parse_float(data.get("other"))

    if all(v is None for v in [qib, nii, retail, total]):
        return None

    source_updated_at = _parse_datetime(data.get("updated_at"))
    if source_updated_at is None:
        source_updated_at = _midnight_fallback(retrieved_at)

    return SubscriptionObservation(
        ipo_id=0,
        retail=retail,
        nii=nii,
        qib=qib,
        employee=employee,
        other=other,
        total=total,
        source=PROVIDER_NAME,
        retrieved_at=retrieved_at,
        source_updated_at=source_updated_at,
    )


# --- Rate limiter ---


class IpoGuruRateLimiter:
    """Enforces IPO Guru API rate limits using persistent storage."""

    def __init__(
        self,
        usage_repo: ApiUsageRepository,
        daily_limit: int = 10,
        min_interval_seconds: int = 60,
        now: datetime | None = None,
    ) -> None:
        self.usage_repo = usage_repo
        self.daily_limit = daily_limit
        self.min_interval_seconds = min_interval_seconds
        self._now = now

    def _get_now(self) -> datetime:
        return self._now or datetime.now(timezone.utc)

    def check(self) -> None:
        """Check if a request is allowed; raise IpoGuruRateLimitError if not."""
        now = self._get_now()
        today = now.date()
        count, last_request_at = self.usage_repo.get_usage(PROVIDER_NAME, today)

        if count >= self.daily_limit:
            raise IpoGuruRateLimitError(
                f"daily limit of {self.daily_limit} requests exceeded"
            )

        if last_request_at is not None and self.min_interval_seconds > 0:
            elapsed = (now - last_request_at).total_seconds()
            if elapsed < self.min_interval_seconds:
                raise IpoGuruRateLimitError(
                    f"minimum interval of {self.min_interval_seconds}s not met "
                    f"(last request {elapsed:.1f}s ago)"
                )

    def record(self) -> int:
        """Record a request and return the new daily count."""
        now = self._get_now()
        today = now.date()
        return self.usage_repo.record(PROVIDER_NAME, today, now)


# --- Result containers ---


@dataclass
class IpoData:
    """Container for a single IPO with its GMP and subscription data."""

    ipo: Ipo
    gmp: GmpObservation | None = None
    subscription: SubscriptionObservation | None = None


@dataclass
class IpoGuruResult:
    """Result from fetching open IPOs."""

    ipo_data: list[IpoData] = field(default_factory=list)
    ipos: list[Ipo] = field(default_factory=list)
    gmp_observations: list[GmpObservation] = field(default_factory=list)
    subscription_observations: list[SubscriptionObservation] = field(default_factory=list)
    requests_used_today: int = 0
    daily_limit: int = 10


# --- Client ---


class IpoGuruClient:
    """Async HTTP client for IPO Guru API."""

    def __init__(
        self,
        settings: Settings,
        usage_repo: ApiUsageRepository,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not settings.ipoguru_api_key:
            raise IpoGuruError("IPOGURU_API_KEY not configured")

        self.settings = settings
        self.usage_repo = usage_repo
        self._http_client = http_client
        self._owns_client = http_client is None
        self._rate_limiter = IpoGuruRateLimiter(
            usage_repo,
            daily_limit=settings.ipoguru_daily_limit,
            min_interval_seconds=settings.ipoguru_min_request_interval_seconds,
        )

    async def __aenter__(self) -> IpoGuruClient:
        if self._owns_client:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._owns_client and self._http_client:
            await self._http_client.aclose()

    async def fetch_open_ipos(self) -> IpoGuruResult:
        """Fetch all currently open IPOs with GMP and subscription data."""
        self._rate_limiter.check()

        retrieved_at = datetime.now(timezone.utc)

        try:
            response = await self._http_client.get(
                f"{API_BASE_URL}/ipos",
                headers={"X-API-KEY": self.settings.ipoguru_api_key},
                params={"status": "open"},
            )
        except httpx.TimeoutException as exc:
            raise IpoGuruError(f"Request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise IpoGuruError(f"HTTP error: {exc}") from exc

        if response.status_code in (401, 403):
            raise IpoGuruAuthError(
                f"Authentication failed: {response.status_code}"
            )
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "unknown")
            raise IpoGuruRateLimitError(
                f"Rate limited, retry after: {retry_after}"
            )
        if response.status_code != 200:
            raise IpoGuruError(
                f"Unexpected status code: {response.status_code}"
            )

        try:
            data = response.json()
        except Exception as exc:
            raise IpoGuruResponseError(
                f"malformed JSON response: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise IpoGuruResponseError("Response is not a JSON object")

        if not data.get("success"):
            raise IpoGuruResponseError("API response indicates failure")

        if "data" not in data:
            raise IpoGuruResponseError("Response missing 'data' field")

        new_count = self._rate_limiter.record()

        ipo_data_list: list[IpoData] = []
        ipos_list: list[Ipo] = []
        gmp_list: list[GmpObservation] = []
        sub_list: list[SubscriptionObservation] = []

        for item in data["data"]:
            if not isinstance(item, dict):
                continue

            ipo = _parse_ipo(item)
            gmp = _parse_gmp(item.get("gmp") or {}, retrieved_at)
            subscription = _parse_subscription(
                item.get("subscription") or {}, retrieved_at
            )

            ipo_data = IpoData(ipo=ipo, gmp=gmp, subscription=subscription)
            ipo_data_list.append(ipo_data)
            ipos_list.append(ipo)
            if gmp:
                gmp_list.append(gmp)
            if subscription:
                sub_list.append(subscription)

        return IpoGuruResult(
            ipo_data=ipo_data_list,
            ipos=ipos_list,
            gmp_observations=gmp_list,
            subscription_observations=sub_list,
            requests_used_today=new_count,
            daily_limit=self.settings.ipoguru_daily_limit,
        )
