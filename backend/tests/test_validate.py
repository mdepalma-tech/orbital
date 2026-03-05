"""Tests for pipeline/validate.py — data integrity gate."""

import pytest
import numpy as np
import pandas as pd

from pipeline.validate import validate_and_prepare, _normalize_date, EPSILON


# ---------------------------------------------------------------------------
# Helper: build a minimal valid dataset (>= 60 rows, non-zero, has variance)
# ---------------------------------------------------------------------------

def _make_timeseries(n=80, revenue_base=500, revenue_noise=200):
    np.random.seed(42)
    dates = pd.date_range("2022-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "ts": dates.strftime("%Y-%m-%dT00:00:00+00:00"),
        "revenue": (revenue_base + np.random.uniform(0, revenue_noise, n)).round(2),
        "orders": np.random.randint(5, 30, n).astype(float),
    })


def _make_spend(n=80):
    np.random.seed(42)
    dates = pd.date_range("2022-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "ts": dates.strftime("%Y-%m-%dT00:00:00+00:00"),
        "meta_spend": np.random.uniform(50, 300, n).round(2),
        "google_spend": np.random.uniform(50, 300, n).round(2),
        "tiktok_spend": np.random.uniform(50, 300, n).round(2),
    })


def _make_events():
    return pd.DataFrame({
        "event_name": ["Launch"],
        "event_type": ["step"],
        "start_ts": ["2022-02-01T00:00:00+00:00"],
        "end_ts": [pd.NaT],
    })


# ---------------------------------------------------------------------------
# _normalize_date tests
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_normalize_date_removes_timezone():
    s = pd.Series(["2022-03-15T14:30:00+05:00"])
    result = _normalize_date(s)
    assert result.dt.tz is None


@pytest.mark.pure
def test_normalize_date_normalizes_to_midnight():
    s = pd.Series(["2022-03-15T14:30:00+00:00"])
    result = _normalize_date(s)
    assert result.iloc[0].hour == 0
    assert result.iloc[0].minute == 0


# ---------------------------------------------------------------------------
# validate_and_prepare — error cases
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_validate_minimum_observations():
    """Fewer than 60 rows should raise ValueError."""
    ts = _make_timeseries(n=30)
    spend = _make_spend(n=30)
    events = _make_events()
    with pytest.raises(ValueError, match="Insufficient data"):
        validate_and_prepare(ts, spend, events)


@pytest.mark.pure
def test_validate_zero_revenue_rejected():
    """All-zero revenue should raise ValueError."""
    ts = _make_timeseries(n=80)
    ts["revenue"] = 0.0
    spend = _make_spend(n=80)
    events = _make_events()
    with pytest.raises(ValueError, match="All revenue values are zero"):
        validate_and_prepare(ts, spend, events)


@pytest.mark.pure
def test_validate_zero_spend_rejected():
    """All-zero spend should raise ValueError."""
    ts = _make_timeseries(n=80)
    spend = _make_spend(n=80)
    spend["meta_spend"] = 0.0
    spend["google_spend"] = 0.0
    spend["tiktok_spend"] = 0.0
    events = _make_events()
    with pytest.raises(ValueError, match="All spend values are zero"):
        validate_and_prepare(ts, spend, events)


@pytest.mark.pure
def test_validate_zero_variance_revenue_rejected():
    """Constant revenue (no variance) should raise ValueError."""
    ts = _make_timeseries(n=80)
    ts["revenue"] = 100.0  # constant — std < EPSILON
    spend = _make_spend(n=80)
    events = _make_events()
    with pytest.raises(ValueError, match="near-zero variance"):
        validate_and_prepare(ts, spend, events)


@pytest.mark.pure
def test_validate_zero_variance_spend_columns_removed():
    """Spend columns with zero variance should be excluded from valid_spend_cols."""
    ts = _make_timeseries(n=80)
    spend = _make_spend(n=80)
    spend["tiktok_spend"] = 100.0  # constant — zero variance
    events = _make_events()
    daily, _, valid_cols = validate_and_prepare(ts, spend, events)
    assert "tiktok_spend" not in valid_cols
    assert "meta_spend" in valid_cols
    assert "google_spend" in valid_cols


@pytest.mark.pure
def test_validate_all_spend_zero_variance_rejected():
    """If all spend columns have zero variance, should raise ValueError."""
    ts = _make_timeseries(n=80)
    spend = _make_spend(n=80)
    spend["meta_spend"] = 100.0
    spend["google_spend"] = 100.0
    spend["tiktok_spend"] = 100.0
    events = _make_events()
    with pytest.raises(ValueError, match="All spend channels have zero variance"):
        validate_and_prepare(ts, spend, events)


# ---------------------------------------------------------------------------
# validate_and_prepare — happy path
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_validate_happy_path_returns_correct_types():
    ts = _make_timeseries(n=80)
    spend = _make_spend(n=80)
    events = _make_events()
    daily, events_out, valid_cols = validate_and_prepare(ts, spend, events)
    assert isinstance(daily, pd.DataFrame)
    assert isinstance(events_out, pd.DataFrame)
    assert isinstance(valid_cols, list)
    assert len(valid_cols) > 0


@pytest.mark.pure
def test_validate_continuous_daily_index():
    """Output should have a gapless daily date range."""
    ts = _make_timeseries(n=80)
    # Remove a few rows to create gaps
    ts = ts.drop(index=[10, 11, 12]).reset_index(drop=True)
    spend = _make_spend(n=80)
    spend = spend.drop(index=[10, 11, 12]).reset_index(drop=True)
    events = _make_events()
    daily, _, _ = validate_and_prepare(ts, spend, events)

    dates = pd.to_datetime(daily["ts"])
    expected = pd.date_range(dates.min(), dates.max(), freq="D")
    assert len(daily) == len(expected), "Daily index should be continuous (no gaps)"


@pytest.mark.pure
def test_validate_missing_dates_filled_with_zero():
    """Gaps in input data should be filled with revenue=0, orders=0."""
    ts = _make_timeseries(n=80)
    # Remove rows 10-12 to create a gap
    ts = ts.drop(index=[10, 11, 12]).reset_index(drop=True)
    spend = _make_spend(n=80)
    spend = spend.drop(index=[10, 11, 12]).reset_index(drop=True)
    events = _make_events()
    daily, _, _ = validate_and_prepare(ts, spend, events)

    # The original gap dates should now have revenue=0
    dates = pd.to_datetime(daily["ts"])
    gap_start = pd.Timestamp("2022-01-11")  # day 10 (0-indexed)
    gap_rows = daily[dates == gap_start]
    assert len(gap_rows) == 1
    assert gap_rows["revenue"].iloc[0] == 0.0


@pytest.mark.pure
def test_validate_events_dates_normalized():
    """Event timestamps should be timezone-naive after validation."""
    ts = _make_timeseries(n=80)
    spend = _make_spend(n=80)
    events = _make_events()
    _, events_out, _ = validate_and_prepare(ts, spend, events)
    if not events_out.empty:
        assert events_out["start_ts"].dt.tz is None
