"""Tests for trend analysis module."""

from datetime import datetime, timezone

import pytest

from app.analysis import (
    Momentum,
    Trend,
    analyze_gmp_history,
    analyze_subscription_history,
    calculate_trend,
)


class TestCalculateTrend:
    """Tests for calculate_trend function."""

    def test_empty_sequence(self):
        """Empty sequence should return insufficient_data."""
        result = calculate_trend([])
        assert result.trend == Trend.INSUFFICIENT_DATA
        assert result.observation_count == 0
        assert result.latest is None
        assert result.previous is None
        assert result.absolute_change is None
        assert result.percentage_change is None
        assert result.momentum == Momentum.INSUFFICIENT_DATA

    def test_single_observation(self):
        """Single observation should return insufficient_data."""
        result = calculate_trend([10.0])
        assert result.trend == Trend.INSUFFICIENT_DATA
        assert result.observation_count == 1
        assert result.latest == 10.0
        assert result.previous is None
        assert result.absolute_change is None
        assert result.percentage_change is None
        assert result.momentum == Momentum.INSUFFICIENT_DATA

    def test_two_observations_rising(self):
        """Two observations with increase should return rising."""
        result = calculate_trend([10.0, 15.0])
        assert result.trend == Trend.RISING
        assert result.observation_count == 2
        assert result.latest == 15.0
        assert result.previous == 10.0
        assert result.absolute_change == 5.0
        assert result.percentage_change == 50.0
        assert result.momentum == Momentum.INSUFFICIENT_DATA

    def test_two_observations_falling(self):
        """Two observations with decrease should return falling."""
        result = calculate_trend([15.0, 10.0])
        assert result.trend == Trend.FALLING
        assert result.observation_count == 2
        assert result.latest == 10.0
        assert result.previous == 15.0
        assert result.absolute_change == -5.0
        assert result.percentage_change == pytest.approx(-33.333333, rel=1e-3)
        assert result.momentum == Momentum.INSUFFICIENT_DATA

    def test_two_observations_flat(self):
        """Two observations with no change should return flat."""
        result = calculate_trend([10.0, 10.0])
        assert result.trend == Trend.FLAT
        assert result.observation_count == 2
        assert result.latest == 10.0
        assert result.previous == 10.0
        assert result.absolute_change == 0.0
        assert result.percentage_change == 0.0

    def test_three_observations_accelerating(self):
        """Three observations with increasing rate should return accelerating."""
        result = calculate_trend([10.0, 12.0, 18.0])
        assert result.trend == Trend.RISING
        assert result.observation_count == 3
        assert result.latest == 18.0
        assert result.previous == 12.0
        assert result.absolute_change == 6.0
        assert result.percentage_change == 50.0
        assert result.momentum == Momentum.ACCELERATING

    def test_three_observations_decelerating(self):
        """Three observations with decreasing rate should return decelerating."""
        result = calculate_trend([10.0, 18.0, 20.0])
        assert result.trend == Trend.RISING
        assert result.observation_count == 3
        assert result.latest == 20.0
        assert result.previous == 18.0
        assert result.absolute_change == 2.0
        assert result.percentage_change == pytest.approx(11.111111, rel=1e-3)
        assert result.momentum == Momentum.DECELERATING

    def test_three_observations_steady(self):
        """Three observations with constant rate should return steady."""
        result = calculate_trend([10.0, 15.0, 20.0])
        assert result.trend == Trend.RISING
        assert result.observation_count == 3
        assert result.latest == 20.0
        assert result.previous == 15.0
        assert result.absolute_change == 5.0
        assert result.percentage_change == pytest.approx(33.333333, rel=1e-3)
        assert result.momentum == Momentum.STEADY

    def test_none_values_filtered(self):
        """None values should be filtered out."""
        result = calculate_trend([None, 10.0, None, 15.0])
        assert result.trend == Trend.RISING
        assert result.observation_count == 2
        assert result.latest == 15.0
        assert result.previous == 10.0

    def test_all_none_values(self):
        """All None values should return insufficient_data."""
        result = calculate_trend([None, None, None])
        assert result.trend == Trend.INSUFFICIENT_DATA
        assert result.observation_count == 0
        assert result.latest is None

    def test_zero_to_positive(self):
        """Change from zero to positive should calculate percentage."""
        result = calculate_trend([0.0, 10.0])
        assert result.trend == Trend.RISING
        assert result.observation_count == 2
        assert result.latest == 10.0
        assert result.previous == 0.0
        assert result.absolute_change == 10.0
        assert result.percentage_change == float('inf')

    def test_positive_to_zero(self):
        """Change from positive to zero should calculate negative percentage."""
        result = calculate_trend([10.0, 0.0])
        assert result.trend == Trend.FALLING
        assert result.observation_count == 2
        assert result.latest == 0.0
        assert result.previous == 10.0
        assert result.absolute_change == -10.0
        assert result.percentage_change == -100.0

    def test_zero_to_zero(self):
        """Change from zero to zero should return flat with None percentage."""
        result = calculate_trend([0.0, 0.0])
        assert result.trend == Trend.FLAT
        assert result.observation_count == 2
        assert result.latest == 0.0
        assert result.previous == 0.0
        assert result.absolute_change == 0.0
        assert result.percentage_change is None
        assert result.momentum == Momentum.INSUFFICIENT_DATA


class TestAnalyzeGmpHistory:
    """Tests for analyze_gmp_history function."""

    def test_empty_observations(self):
        """Empty observations should return insufficient_data."""
        result = analyze_gmp_history(1, "Test IPO", [])
        assert result.ipo_id == 1
        assert result.company_name == "Test IPO"
        assert result.trend_result.trend == Trend.INSUFFICIENT_DATA
        assert result.gmp_percentage is None
        assert result.source_updated_at is None

    def test_single_observation(self):
        """Single observation should return insufficient_data."""
        obs = [
            {
                "gmp": 10.0,
                "gmp_percentage": 5.0,
                "estimated_listing_price": 210.0,
                "source_updated_at": "2024-01-01T10:00:00Z",
            }
        ]
        result = analyze_gmp_history(1, "Test IPO", obs)
        assert result.trend_result.trend == Trend.INSUFFICIENT_DATA
        assert result.trend_result.latest == 10.0
        assert result.gmp_percentage == 5.0
        assert result.estimated_listing_price == 210.0
        assert result.source_updated_at == "2024-01-01T10:00:00Z"

    def test_rising_gmp(self):
        """Rising GMP should be detected."""
        obs = [
            {"gmp": 10.0, "gmp_percentage": 5.0, "source_updated_at": "2024-01-01T10:00:00Z"},
            {"gmp": 15.0, "gmp_percentage": 7.5, "source_updated_at": "2024-01-02T10:00:00Z"},
        ]
        result = analyze_gmp_history(1, "Test IPO", obs)
        assert result.trend_result.trend == Trend.RISING
        assert result.trend_result.latest == 15.0
        assert result.gmp_percentage == 7.5

    def test_explicit_zero_gmp(self):
        """Explicit zero GMP should be treated as zero, not missing."""
        obs = [
            {"gmp": 0.0, "gmp_percentage": 0.0, "source_updated_at": "2024-01-01T10:00:00Z"},
            {"gmp": 5.0, "gmp_percentage": 2.5, "source_updated_at": "2024-01-02T10:00:00Z"},
        ]
        result = analyze_gmp_history(1, "Test IPO", obs)
        assert result.trend_result.trend == Trend.RISING
        assert result.trend_result.previous == 0.0
        assert result.trend_result.latest == 5.0


class TestAnalyzeSubscriptionHistory:
    """Tests for analyze_subscription_history function."""

    def test_empty_observations(self):
        """Empty observations should return insufficient_data for all categories."""
        result = analyze_subscription_history(1, "Test IPO", [])
        assert result.ipo_id == 1
        assert result.company_name == "Test IPO"
        assert result.qib.trend_result.trend == Trend.INSUFFICIENT_DATA
        assert result.nii.trend_result.trend == Trend.INSUFFICIENT_DATA
        assert result.retail.trend_result.trend == Trend.INSUFFICIENT_DATA
        assert result.total.trend_result.trend == Trend.INSUFFICIENT_DATA

    def test_single_observation(self):
        """Single observation should return insufficient_data."""
        obs = [
            {
                "qib": 1.5,
                "nii": 2.0,
                "retail": 3.0,
                "total": 2.5,
                "source_updated_at": "2024-01-01T10:00:00Z",
            }
        ]
        result = analyze_subscription_history(1, "Test IPO", obs)
        assert result.qib.trend_result.trend == Trend.INSUFFICIENT_DATA
        assert result.qib.trend_result.latest == 1.5
        assert result.nii.trend_result.latest == 2.0
        assert result.retail.trend_result.latest == 3.0
        assert result.total.trend_result.latest == 2.5

    def test_rising_subscription(self):
        """Rising subscription should be detected."""
        obs = [
            {"qib": 1.0, "nii": 1.5, "retail": 2.0, "total": 1.5, "source_updated_at": "2024-01-01T10:00:00Z"},
            {"qib": 2.0, "nii": 3.0, "retail": 4.0, "total": 3.0, "source_updated_at": "2024-01-02T10:00:00Z"},
        ]
        result = analyze_subscription_history(1, "Test IPO", obs)
        assert result.qib.trend_result.trend == Trend.RISING
        assert result.nii.trend_result.trend == Trend.RISING
        assert result.retail.trend_result.trend == Trend.RISING
        assert result.total.trend_result.trend == Trend.RISING

    def test_mixed_trends(self):
        """Different categories can have different trends."""
        obs = [
            {"qib": 1.0, "nii": 2.0, "retail": 3.0, "total": 2.0, "source_updated_at": "2024-01-01T10:00:00Z"},
            {"qib": 2.0, "nii": 1.5, "retail": 3.0, "total": 2.5, "source_updated_at": "2024-01-02T10:00:00Z"},
        ]
        result = analyze_subscription_history(1, "Test IPO", obs)
        assert result.qib.trend_result.trend == Trend.RISING
        assert result.nii.trend_result.trend == Trend.FALLING
        assert result.retail.trend_result.trend == Trend.FLAT
        assert result.total.trend_result.trend == Trend.RISING

    def test_missing_category(self):
        """Missing category should be treated as None."""
        obs = [
            {"qib": 1.0, "nii": None, "retail": 2.0, "total": 1.5, "source_updated_at": "2024-01-01T10:00:00Z"},
            {"qib": 2.0, "nii": None, "retail": 3.0, "total": 2.5, "source_updated_at": "2024-01-02T10:00:00Z"},
        ]
        result = analyze_subscription_history(1, "Test IPO", obs)
        assert result.qib.trend_result.trend == Trend.RISING
        assert result.nii.trend_result.trend == Trend.INSUFFICIENT_DATA
        assert result.retail.trend_result.trend == Trend.RISING


class TestMomentum:
    """Tests for momentum calculation."""

    def test_momentum_with_three_rising_values(self):
        """Three rising values should calculate momentum."""
        obs = [
            {"gmp": 10.0, "source_updated_at": "2024-01-01T10:00:00Z"},
            {"gmp": 12.0, "source_updated_at": "2024-01-02T10:00:00Z"},
            {"gmp": 18.0, "source_updated_at": "2024-01-03T10:00:00Z"},
        ]
        result = analyze_gmp_history(1, "Test IPO", obs)
        assert result.trend_result.trend == Trend.RISING
        assert result.trend_result.momentum == Momentum.ACCELERATING

    def test_momentum_decelerating(self):
        """Decelerating growth should be detected."""
        obs = [
            {"gmp": 10.0, "source_updated_at": "2024-01-01T10:00:00Z"},
            {"gmp": 18.0, "source_updated_at": "2024-01-02T10:00:00Z"},
            {"gmp": 20.0, "source_updated_at": "2024-01-03T10:00:00Z"},
        ]
        result = analyze_gmp_history(1, "Test IPO", obs)
        assert result.trend_result.trend == Trend.RISING
        assert result.trend_result.momentum == Momentum.DECELERATING

    def test_momentum_steady(self):
        """Steady growth should be detected."""
        obs = [
            {"gmp": 10.0, "source_updated_at": "2024-01-01T10:00:00Z"},
            {"gmp": 15.0, "source_updated_at": "2024-01-02T10:00:00Z"},
            {"gmp": 20.0, "source_updated_at": "2024-01-03T10:00:00Z"},
        ]
        result = analyze_gmp_history(1, "Test IPO", obs)
        assert result.trend_result.trend == Trend.RISING
        assert result.trend_result.momentum == Momentum.STEADY

    def test_subscription_momentum(self):
        """Subscription momentum should be calculated independently."""
        obs = [
            {"qib": 1.0, "nii": 1.0, "retail": 1.0, "total": 1.0, "source_updated_at": "2024-01-01T10:00:00Z"},
            {"qib": 2.5, "nii": 2.0, "retail": 1.5, "total": 2.0, "source_updated_at": "2024-01-02T10:00:00Z"},
            {"qib": 6.0, "nii": 3.5, "retail": 2.0, "total": 3.5, "source_updated_at": "2024-01-03T10:00:00Z"},
        ]
        result = analyze_subscription_history(1, "Test IPO", obs)
        assert result.qib.trend_result.momentum == Momentum.ACCELERATING
        assert result.nii.trend_result.momentum == Momentum.ACCELERATING
        assert result.retail.trend_result.momentum == Momentum.STEADY
        assert result.total.trend_result.momentum == Momentum.ACCELERATING


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_duplicate_source_timestamp(self):
        """Duplicate source timestamps should still be counted as observations."""
        obs = [
            {"gmp": 10.0, "source_updated_at": "2024-01-01T10:00:00Z"},
            {"gmp": 10.0, "source_updated_at": "2024-01-01T10:00:00Z"},
        ]
        result = analyze_gmp_history(1, "Test IPO", obs)
        assert result.trend_result.observation_count == 2
        assert result.trend_result.trend == Trend.FLAT

    def test_different_source_timestamps(self):
        """Different source timestamps should create separate observations."""
        obs = [
            {"gmp": 10.0, "source_updated_at": "2024-01-01T10:00:00Z"},
            {"gmp": 15.0, "source_updated_at": "2024-01-02T10:00:00Z"},
        ]
        result = analyze_gmp_history(1, "Test IPO", obs)
        assert result.trend_result.observation_count == 2
        assert result.trend_result.trend == Trend.RISING

    def test_large_number_of_observations(self):
        """Should handle large number of observations."""
        obs = [
            {"gmp": float(i), "source_updated_at": f"2024-01-{(i % 28) + 1:02d}T10:00:00Z"}
            for i in range(100)
        ]
        result = analyze_gmp_history(1, "Test IPO", obs)
        assert result.trend_result.observation_count == 100
        assert result.trend_result.latest == 99.0
        assert result.trend_result.trend == Trend.RISING
