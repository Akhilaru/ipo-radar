"""Trend analysis for GMP and subscription observations.

This module provides read-only trend calculations from historical observations.
All calculations are deterministic and transparent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Sequence


class Trend(StrEnum):
    """Trend direction."""
    RISING = "rising"
    FALLING = "falling"
    FLAT = "flat"
    INSUFFICIENT_DATA = "insufficient_data"


class Momentum(StrEnum):
    """Momentum classification."""
    ACCELERATING = "accelerating"
    DECELERATING = "decelerating"
    STEADY = "steady"
    INSUFFICIENT_DATA = "insufficient_data"


class Freshness(StrEnum):
    """Data freshness classification based on age."""
    FRESH = "fresh"      # < 6 hours
    AGING = "aging"      # 6-24 hours
    STALE = "stale"      # > 24 hours


# Freshness thresholds in seconds
FRESH_THRESHOLD = 6 * 60 * 60      # 6 hours
AGING_THRESHOLD = 24 * 60 * 60     # 24 hours


@dataclass(frozen=True)
class TrendResult:
    """Result of trend analysis."""
    first: float | None
    latest: float | None
    previous: float | None
    absolute_change: float | None
    percentage_change: float | None
    absolute_change_from_first: float | None
    percentage_change_from_first: float | None
    latest_direction: Trend
    overall_direction: Trend
    momentum: Momentum
    observation_count: int

    @property
    def has_sufficient_data(self) -> bool:
        """Check if there's enough data for trend analysis."""
        return self.observation_count >= 2

    @property
    def has_momentum_data(self) -> bool:
        """Check if there's enough data for momentum analysis."""
        return self.observation_count >= 3


def calculate_trend(values: Sequence[float | None]) -> TrendResult:
    """Calculate trend from a sequence of observations.
    
    Args:
        values: Sequence of observation values (oldest to newest)
        
    Returns:
        TrendResult with trend analysis
    """
    # Filter out None values
    valid_values = [v for v in values if v is not None]
    count = len(valid_values)
    
    if count == 0:
        return TrendResult(
            first=None,
            latest=None,
            previous=None,
            absolute_change=None,
            percentage_change=None,
            absolute_change_from_first=None,
            percentage_change_from_first=None,
            latest_direction=Trend.INSUFFICIENT_DATA,
            overall_direction=Trend.INSUFFICIENT_DATA,
            momentum=Momentum.INSUFFICIENT_DATA,
            observation_count=0,
        )
    
    first = valid_values[0]
    latest = valid_values[-1]
    previous = valid_values[-2] if count >= 2 else None
    
    # Calculate changes from previous
    if previous is not None:
        absolute_change = latest - previous
        percentage_change = _safe_percentage_change(absolute_change, previous)
    else:
        absolute_change = None
        percentage_change = None
    
    # Calculate changes from first
    if count >= 2 and first is not None:
        absolute_change_from_first = latest - first
        percentage_change_from_first = _safe_percentage_change(absolute_change_from_first, first)
    else:
        absolute_change_from_first = None
        percentage_change_from_first = None
    
    # Determine latest direction (previous → latest)
    if count < 2:
        latest_direction = Trend.INSUFFICIENT_DATA
    elif latest > previous:
        latest_direction = Trend.RISING
    elif latest < previous:
        latest_direction = Trend.FALLING
    else:
        latest_direction = Trend.FLAT
    
    # Determine overall direction (first → latest)
    if count < 2:
        overall_direction = Trend.INSUFFICIENT_DATA
    elif latest > first:
        overall_direction = Trend.RISING
    elif latest < first:
        overall_direction = Trend.FALLING
    else:
        overall_direction = Trend.FLAT
    
    # Calculate momentum (requires 3+ observations)
    momentum = _calculate_momentum(valid_values)
    
    return TrendResult(
        first=first,
        latest=latest,
        previous=previous,
        absolute_change=absolute_change,
        percentage_change=percentage_change,
        absolute_change_from_first=absolute_change_from_first,
        percentage_change_from_first=percentage_change_from_first,
        latest_direction=latest_direction,
        overall_direction=overall_direction,
        momentum=momentum,
        observation_count=count,
    )


def _safe_percentage_change(absolute_change: float, base_value: float) -> float | None:
    """Calculate percentage change safely, returning None for zero division.
    
    Args:
        absolute_change: The absolute difference
        base_value: The base value to calculate percentage from
        
    Returns:
        Percentage change or None if base_value is zero
    """
    if base_value == 0:
        # If both values are zero, percentage change is 0
        # Otherwise, percentage change is undefined
        return 0.0 if absolute_change == 0 else None
    return (absolute_change / base_value) * 100


def _calculate_momentum(values: Sequence[float]) -> Momentum:
    """Calculate momentum from 3+ observations."""
    if len(values) < 3:
        return Momentum.INSUFFICIENT_DATA
    
    v1, v2, v3 = values[-3], values[-2], values[-1]
    change1 = v2 - v1
    change2 = v3 - v2
    
    if change2 > change1:
        return Momentum.ACCELERATING
    elif change2 < change1:
        return Momentum.DECELERATING
    else:
        return Momentum.STEADY


def calculate_freshness(timestamp: str | None, analysis_time: datetime) -> Freshness:
    """Calculate freshness for an ISO timestamp relative to analysis_time.

    Fresh is under 6 hours, aging is 6-24 hours, and stale is 24 hours or older.
    """
    if timestamp is None:
        return Freshness.STALE
    
    try:
        # Parse ISO 8601 timestamp
        source_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        # Calculate age in seconds
        age_seconds = (analysis_time - source_time).total_seconds()
        
        if age_seconds < FRESH_THRESHOLD:
            return Freshness.FRESH
        elif age_seconds < AGING_THRESHOLD:
            return Freshness.AGING
        else:
            return Freshness.STALE
    except (ValueError, TypeError):
        return Freshness.STALE


@dataclass(frozen=True)
class GmpAnalysis:
    """Complete GMP analysis for an IPO."""
    ipo_id: int
    company_name: str
    trend_result: TrendResult
    gmp_percentage: float | None = None
    estimated_listing_price: float | None = None
    source_updated_at: str | None = None
    retrieved_at: str | None = None
    source_freshness: Freshness = Freshness.STALE
    collection_freshness: Freshness = Freshness.STALE
    # Backward-compatible alias for callers that used the old field.
    freshness: Freshness = Freshness.STALE


@dataclass(frozen=True)
class SubscriptionCategoryAnalysis:
    """Analysis for a single subscription category."""
    category: str  # "qib", "nii", "retail", "total"
    trend_result: TrendResult


@dataclass(frozen=True)
class SubscriptionAnalysis:
    """Complete subscription analysis for an IPO."""
    ipo_id: int
    company_name: str
    qib: SubscriptionCategoryAnalysis
    nii: SubscriptionCategoryAnalysis
    retail: SubscriptionCategoryAnalysis
    total: SubscriptionCategoryAnalysis
    source_updated_at: str | None = None
    retrieved_at: str | None = None
    source_freshness: Freshness = Freshness.STALE
    collection_freshness: Freshness = Freshness.STALE
    # Backward-compatible alias for callers that used the old field.
    freshness: Freshness = Freshness.STALE


def analyze_gmp_history(
    ipo_id: int,
    company_name: str,
    observations: Sequence[dict],
    analysis_time: datetime | None = None,
) -> GmpAnalysis:
    """Analyze GMP history for an IPO.
    
    Args:
        ipo_id: IPO identifier
        company_name: Company name for display
        observations: Sequence of GMP observation dicts
        analysis_time: Current analysis time (defaults to UTC now)
        
    Returns:
        GmpAnalysis with trend and freshness analysis
    """
    if analysis_time is None:
        analysis_time = datetime.now(timezone.utc)
    
    gmp_values = [obs.get("gmp") for obs in observations]
    trend_result = calculate_trend(gmp_values)
    
    latest_obs = observations[-1] if observations else {}
    source_updated_at = latest_obs.get("source_updated_at")
    retrieved_at = latest_obs.get("retrieved_at")
    source_freshness = calculate_freshness(source_updated_at, analysis_time)
    collection_freshness = calculate_freshness(retrieved_at, analysis_time)
    
    return GmpAnalysis(
        ipo_id=ipo_id,
        company_name=company_name,
        trend_result=trend_result,
        gmp_percentage=latest_obs.get("gmp_percentage"),
        estimated_listing_price=latest_obs.get("estimated_listing_price"),
        source_updated_at=source_updated_at,
        retrieved_at=retrieved_at,
        source_freshness=source_freshness,
        collection_freshness=collection_freshness,
        freshness=source_freshness,
    )


def analyze_subscription_history(
    ipo_id: int,
    company_name: str,
    observations: Sequence[dict],
    analysis_time: datetime | None = None,
) -> SubscriptionAnalysis:
    """Analyze subscription history for an IPO.
    
    Args:
        ipo_id: IPO identifier
        company_name: Company name for display
        observations: Sequence of subscription observation dicts
        analysis_time: Current analysis time (defaults to UTC now)
        
    Returns:
        SubscriptionAnalysis with trend and freshness analysis
    """
    if analysis_time is None:
        analysis_time = datetime.now(timezone.utc)
    
    qib_values = [obs.get("qib") for obs in observations]
    nii_values = [obs.get("nii") for obs in observations]
    retail_values = [obs.get("retail") for obs in observations]
    total_values = [obs.get("total") for obs in observations]
    
    latest_obs = observations[-1] if observations else {}
    source_updated_at = latest_obs.get("source_updated_at")
    retrieved_at = latest_obs.get("retrieved_at")
    source_freshness = calculate_freshness(source_updated_at, analysis_time)
    collection_freshness = calculate_freshness(retrieved_at, analysis_time)
    
    return SubscriptionAnalysis(
        ipo_id=ipo_id,
        company_name=company_name,
        qib=SubscriptionCategoryAnalysis(
            category="qib",
            trend_result=calculate_trend(qib_values),
        ),
        nii=SubscriptionCategoryAnalysis(
            category="nii",
            trend_result=calculate_trend(nii_values),
        ),
        retail=SubscriptionCategoryAnalysis(
            category="retail",
            trend_result=calculate_trend(retail_values),
        ),
        total=SubscriptionCategoryAnalysis(
            category="total",
            trend_result=calculate_trend(total_values),
        ),
        source_updated_at=source_updated_at,
        retrieved_at=retrieved_at,
        source_freshness=source_freshness,
        collection_freshness=collection_freshness,
        freshness=source_freshness,
    )




