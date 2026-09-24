"""Trend analysis for GMP and subscription observations.

This module provides read-only trend calculations from historical observations.
All calculations are deterministic and transparent.
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class TrendResult:
    """Result of trend analysis."""
    latest: float | None
    previous: float | None
    absolute_change: float | None
    percentage_change: float | None
    observation_count: int
    trend: Trend
    momentum: Momentum = Momentum.INSUFFICIENT_DATA

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
            latest=None,
            previous=None,
            absolute_change=None,
            percentage_change=None,
            observation_count=0,
            trend=Trend.INSUFFICIENT_DATA,
            momentum=Momentum.INSUFFICIENT_DATA,
        )
    
    latest = valid_values[-1]
    previous = valid_values[-2] if count >= 2 else None
    
    # Calculate changes
    if previous is not None:
        absolute_change = latest - previous
        if previous != 0:
            percentage_change = (absolute_change / previous) * 100
        else:
            percentage_change = None if latest == 0 else float('inf')
    else:
        absolute_change = None
        percentage_change = None
    
    # Determine trend
    if count < 2:
        trend = Trend.INSUFFICIENT_DATA
    elif latest > previous:
        trend = Trend.RISING
    elif latest < previous:
        trend = Trend.FALLING
    else:
        trend = Trend.FLAT
    
    # Calculate momentum (requires 3+ observations)
    momentum = _calculate_momentum(valid_values)
    
    return TrendResult(
        latest=latest,
        previous=previous,
        absolute_change=absolute_change,
        percentage_change=percentage_change,
        observation_count=count,
        trend=trend,
        momentum=momentum,
    )


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


@dataclass(frozen=True)
class GmpAnalysis:
    """Complete GMP analysis for an IPO."""
    ipo_id: int
    company_name: str
    trend_result: TrendResult
    gmp_percentage: float | None = None
    estimated_listing_price: float | None = None
    source_updated_at: str | None = None


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


def analyze_gmp_history(
    ipo_id: int,
    company_name: str,
    observations: Sequence[dict],
) -> GmpAnalysis:
    """Analyze GMP history for an IPO."""
    gmp_values = [obs.get("gmp") for obs in observations]
    trend_result = calculate_trend(gmp_values)
    
    latest_obs = observations[-1] if observations else {}
    
    return GmpAnalysis(
        ipo_id=ipo_id,
        company_name=company_name,
        trend_result=trend_result,
        gmp_percentage=latest_obs.get("gmp_percentage"),
        estimated_listing_price=latest_obs.get("estimated_listing_price"),
        source_updated_at=latest_obs.get("source_updated_at"),
    )


def analyze_subscription_history(
    ipo_id: int,
    company_name: str,
    observations: Sequence[dict],
) -> SubscriptionAnalysis:
    """Analyze subscription history for an IPO."""
    qib_values = [obs.get("qib") for obs in observations]
    nii_values = [obs.get("nii") for obs in observations]
    retail_values = [obs.get("retail") for obs in observations]
    total_values = [obs.get("total") for obs in observations]
    
    latest_obs = observations[-1] if observations else {}
    
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
        source_updated_at=latest_obs.get("source_updated_at"),
    )

