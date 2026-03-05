"""Tests for pipeline/aggregate.py — event dummies and weekly aggregation."""

import pytest
import numpy as np
import pandas as pd

from pipeline.aggregate import apply_event_dummies, aggregate_to_weekly


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_daily(n_days=28, start="2022-01-03"):
    """Build a simple daily DataFrame starting on a Monday."""
    np.random.seed(42)
    dates = pd.date_range(start, periods=n_days, freq="D")
    return pd.DataFrame({
        "ts": dates,
        "revenue": np.random.uniform(100, 500, n_days).round(2),
        "orders": np.random.randint(5, 20, n_days).astype(float),
        "meta_spend": np.random.uniform(50, 200, n_days).round(2),
        "google_spend": np.random.uniform(50, 200, n_days).round(2),
    })


# ---------------------------------------------------------------------------
# apply_event_dummies
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_apply_event_dummies_step_event():
    """Step event: 0 before start, 1.0 from start onward."""
    df = _make_daily(n_days=30)
    events = pd.DataFrame({
        "event_name": ["Launch"],
        "event_type": ["step"],
        "start_ts": [pd.Timestamp("2022-01-10")],
        "end_ts": [pd.NaT],
    })
    result = apply_event_dummies(df, events)
    assert "event_launch" in result.columns
    before = result[result["ts"] < pd.Timestamp("2022-01-10")]["event_launch"]
    after = result[result["ts"] >= pd.Timestamp("2022-01-10")]["event_launch"]
    assert (before == 0.0).all()
    assert (after == 1.0).all()


@pytest.mark.pure
def test_apply_event_dummies_pulse_event_with_end():
    """Pulse event with end_ts: 1.0 only within [start, end]."""
    df = _make_daily(n_days=30)
    events = pd.DataFrame({
        "event_name": ["Promo"],
        "event_type": ["pulse"],
        "start_ts": [pd.Timestamp("2022-01-10")],
        "end_ts": [pd.Timestamp("2022-01-15")],
    })
    result = apply_event_dummies(df, events)
    col = "event_promo"
    assert col in result.columns
    in_range = result[
        (result["ts"] >= pd.Timestamp("2022-01-10"))
        & (result["ts"] <= pd.Timestamp("2022-01-15"))
    ][col]
    out_range = result[
        (result["ts"] < pd.Timestamp("2022-01-10"))
        | (result["ts"] > pd.Timestamp("2022-01-15"))
    ][col]
    assert (in_range == 1.0).all()
    assert (out_range == 0.0).all()


@pytest.mark.pure
def test_apply_event_dummies_pulse_event_no_end():
    """Pulse event without end_ts: 1.0 only on the start date."""
    df = _make_daily(n_days=30)
    events = pd.DataFrame({
        "event_name": ["Flash"],
        "event_type": ["pulse"],
        "start_ts": [pd.Timestamp("2022-01-10")],
        "end_ts": [pd.NaT],
    })
    result = apply_event_dummies(df, events)
    col = "event_flash"
    assert result[col].sum() == 1.0  # only one day flagged
    assert result.loc[result["ts"] == pd.Timestamp("2022-01-10"), col].iloc[0] == 1.0


@pytest.mark.pure
def test_apply_event_dummies_empty_events():
    """Empty events DataFrame returns the original DataFrame unchanged."""
    df = _make_daily(n_days=14)
    events = pd.DataFrame(columns=["event_name", "event_type", "start_ts", "end_ts"])
    result = apply_event_dummies(df, events)
    assert list(result.columns) == list(df.columns)


@pytest.mark.pure
def test_apply_event_dummies_column_naming():
    """Column name should be event_{lowercase_underscore_name}."""
    df = _make_daily(n_days=14)
    events = pd.DataFrame({
        "event_name": ["Black Friday Sale"],
        "event_type": ["pulse"],
        "start_ts": [pd.Timestamp("2022-01-05")],
        "end_ts": [pd.Timestamp("2022-01-06")],
    })
    result = apply_event_dummies(df, events)
    assert "event_black_friday_sale" in result.columns


# ---------------------------------------------------------------------------
# aggregate_to_weekly
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_aggregate_to_weekly_sums_revenue_and_spend():
    """Revenue and spend should be summed per week. Total weekly sum == total daily sum."""
    df = _make_daily(n_days=14, start="2022-01-03")  # 2 full weeks starting Monday
    spend_cols = ["meta_spend", "google_spend"]
    weekly = aggregate_to_weekly(df, spend_cols)

    # Total across all weeks should equal total across all days
    assert abs(weekly["revenue"].sum() - df["revenue"].sum()) < 0.01
    for col in spend_cols:
        assert abs(weekly[col].sum() - df[col].sum()) < 0.01


@pytest.mark.pure
def test_aggregate_to_weekly_events_use_max():
    """Event columns should be propagated via max (1.0 if any day in week had event)."""
    df = _make_daily(n_days=21, start="2022-01-03")  # 3 full weeks Mon-Sun
    events = pd.DataFrame({
        "event_name": ["Sale"],
        "event_type": ["pulse"],
        "start_ts": [pd.Timestamp("2022-01-05")],  # Wednesday of week 1
        "end_ts": [pd.Timestamp("2022-01-05")],
    })
    df = apply_event_dummies(df, events)
    spend_cols = ["meta_spend", "google_spend"]
    weekly = aggregate_to_weekly(df, spend_cols)
    # The week containing 2022-01-05 should have event_sale=1.0
    event_week = weekly[weekly["event_sale"] == 1.0]
    assert len(event_week) == 1
    # At least one week should have event_sale=0.0
    non_event_weeks = weekly[weekly["event_sale"] == 0.0]
    assert len(non_event_weeks) >= 1


@pytest.mark.pure
def test_aggregate_to_weekly_partial_first_week_dropped():
    """When first week has fewer than 7 days, it should be removed."""
    # Start on Wednesday — first week only has 5 days (Wed-Sun)
    df = _make_daily(n_days=28, start="2022-01-05")
    spend_cols = ["meta_spend", "google_spend"]
    weekly = aggregate_to_weekly(df, spend_cols)
    # All week_start dates should be Mondays
    for ws in weekly["week_start"]:
        assert ws.dayofweek == 0, f"{ws} is not a Monday"
    # First row should NOT contain the partial week
    assert weekly["week_start"].iloc[0] >= pd.Timestamp("2022-01-10")


@pytest.mark.pure
def test_aggregate_to_weekly_full_first_week_kept():
    """When first week starts on Monday (full 7 days), it is retained."""
    df = _make_daily(n_days=21, start="2022-01-03")  # Monday
    spend_cols = ["meta_spend", "google_spend"]
    weekly = aggregate_to_weekly(df, spend_cols)
    assert weekly["week_start"].iloc[0] == pd.Timestamp("2022-01-03")


@pytest.mark.pure
def test_aggregate_to_weekly_week_index_sequential():
    """week_index should be 0, 1, 2, ... even after partial-week removal."""
    df = _make_daily(n_days=35, start="2022-01-05")  # Wednesday — partial first week
    spend_cols = ["meta_spend", "google_spend"]
    weekly = aggregate_to_weekly(df, spend_cols)
    expected_index = list(range(len(weekly)))
    assert list(weekly["week_index"]) == expected_index


@pytest.mark.pure
def test_aggregate_to_weekly_frequency_is_w_mon():
    """All week_start dates should be Mondays."""
    df = _make_daily(n_days=42, start="2022-01-03")
    spend_cols = ["meta_spend", "google_spend"]
    weekly = aggregate_to_weekly(df, spend_cols)
    for ws in weekly["week_start"]:
        assert ws.dayofweek == 0, f"Expected Monday, got {ws} (day {ws.dayofweek})"
