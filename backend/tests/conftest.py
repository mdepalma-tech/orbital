"""Shared fixtures for the Orbital pipeline test suite.

All fixtures use np.random.seed(42) for reproducibility.
No live Supabase connection required.
"""

import os

# Set dummy env vars BEFORE any pipeline module imports config.py.
# config.py reads these at import time, so they must exist during collection.
os.environ.setdefault("NEXT_PUBLIC_SUPABASE_URL", "http://localhost:0")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")

import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Fixture 1: Raw synthetic data (mimics what fetch_project_data returns)
# ---------------------------------------------------------------------------

@pytest.fixture
def daily_data():
    """120 days of synthetic timeseries + spend + events data."""
    np.random.seed(42)
    n_days = 120
    dates = pd.date_range("2022-01-03", periods=n_days, freq="D")  # starts Monday

    # Revenue with some variance
    revenue = 500 + np.random.uniform(0, 200, n_days)
    orders = (revenue / np.random.uniform(15, 25, n_days)).round()

    timeseries = pd.DataFrame({
        "ts": dates.strftime("%Y-%m-%dT00:00:00+00:00"),  # UTC string like Supabase
        "revenue": revenue.round(2),
        "orders": orders,
    })

    spend = pd.DataFrame({
        "ts": dates.strftime("%Y-%m-%dT00:00:00+00:00"),
        "meta_spend": np.random.uniform(50, 500, n_days).round(2),
        "google_spend": np.random.uniform(50, 500, n_days).round(2),
        "tiktok_spend": np.random.uniform(50, 500, n_days).round(2),
    })

    events = pd.DataFrame({
        "event_name": ["Launch", "Promo"],
        "event_type": ["step", "pulse"],
        "start_ts": [
            "2022-02-01T00:00:00+00:00",
            "2022-02-20T00:00:00+00:00",
        ],
        "end_ts": [
            pd.NaT,
            "2022-02-27T00:00:00+00:00",
        ],
    })

    return timeseries, spend, events


# ---------------------------------------------------------------------------
# Fixture 2: Validated daily DataFrame (output of validate_and_prepare)
# ---------------------------------------------------------------------------

@pytest.fixture
def validated_daily(daily_data):
    """Run validation on the synthetic data. Returns (daily_df, events, spend_cols)."""
    from pipeline.validate import validate_and_prepare
    timeseries, spend, events = daily_data
    return validate_and_prepare(timeseries, spend, events)


# ---------------------------------------------------------------------------
# Fixture 3: Weekly aggregated DataFrame
# ---------------------------------------------------------------------------

@pytest.fixture
def weekly_data(validated_daily):
    """Aggregate validated daily data to weekly. Returns (df_weekly, spend_cols)."""
    from pipeline.aggregate import apply_event_dummies, aggregate_to_weekly
    daily_df, events, spend_cols = validated_daily
    daily_with_events = apply_event_dummies(daily_df, events)
    df_weekly = aggregate_to_weekly(daily_with_events, spend_cols)
    return df_weekly, spend_cols


# ---------------------------------------------------------------------------
# Fixture 4: Fitted OLS model result
# ---------------------------------------------------------------------------

@pytest.fixture
def fitted_result(weekly_data):
    """Fit an OLS model on the weekly data. Returns (result, X, y, spend_cols)."""
    from pipeline.matrix import build_design_matrix
    from pipeline.modeling import fit_ols
    df_weekly, spend_cols = weekly_data
    X, y, feature_state = build_design_matrix(df_weekly, spend_cols)
    result = fit_ols(X, y)
    return result, X, y, spend_cols


# ---------------------------------------------------------------------------
# Fixture 5: Mock Supabase client
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_supabase(monkeypatch):
    """Replace get_supabase() with a MagicMock. Returns the mock client.

    Patches at every import site so the mock takes effect regardless of which
    module calls get_supabase().
    """
    mock_sb = MagicMock()

    # Set up fluent API chain: sb.table("x").select("y").eq("z", v).execute()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.single.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[])

    _mock_fn = lambda: mock_sb
    # Patch at the source module and every import site
    monkeypatch.setattr("services.supabase_client.get_supabase", _mock_fn)
    monkeypatch.setattr("pipeline.fetch.get_supabase", _mock_fn)
    monkeypatch.setattr("pipeline.persist.get_supabase", _mock_fn)

    return mock_sb
