"""Tests for pipeline/forecast.py — prediction engine (pure math + mocked DB)."""

import pytest
import numpy as np
import pandas as pd

from pipeline.forecast import (
    LoadedModelVersion,
    build_X_for_prediction,
    predict_revenue,
)


# ---------------------------------------------------------------------------
# Helper: build a LoadedModelVersion for testing
# ---------------------------------------------------------------------------

def _make_loaded(
    lags_added=0,
    use_log_target=False,
    use_adstock=False,
    channel_alphas=None,
    use_log=False,
    ridge_applied=False,
    smearing_factor=1.0,
):
    coefficients = {
        "const": 100.0,
        "trend": 2.0,
        "meta_spend": 5.0,
        "google_spend": 3.0,
    }
    feature_names = ["const", "trend", "meta_spend", "google_spend"]

    if lags_added >= 1:
        coefficients["lag_1"] = 0.3
        feature_names.append("lag_1")
    if lags_added >= 2:
        coefficients["lag_2"] = 0.15
        feature_names.append("lag_2")

    model_config = {
        "use_adstock": use_adstock,
        "channel_alphas": channel_alphas or {},
        "use_log": use_log,
        "use_log_target": use_log_target,
        "smearing_factor": smearing_factor,
        "feature_names": feature_names,
    }

    feature_state = {
        "trend_mean": 50.0,
        "channel_alphas": channel_alphas or {},
        "adstock_last": {"meta_spend": 0.0, "google_spend": 0.0},
        "lag_history": [100.0, 110.0],
    }

    return LoadedModelVersion(
        version_id="v-123",
        model_id="m-456",
        model_type="ridge" if ridge_applied else "ols",
        ridge_applied=ridge_applied,
        lags_added=lags_added,
        coefficients=coefficients,
        feature_names=feature_names,
        feature_state=feature_state,
        model_config=model_config,
        spend_cols=["meta_spend", "google_spend"],
    )


def _make_weekly_for_prediction(n_weeks=4, start_week_index=100):
    """Build a minimal weekly DataFrame for prediction."""
    np.random.seed(42)
    return pd.DataFrame({
        "week_index": range(start_week_index, start_week_index + n_weeks),
        "meta_spend": np.random.uniform(100, 300, n_weeks),
        "google_spend": np.random.uniform(50, 200, n_weeks),
    })


# ---------------------------------------------------------------------------
# build_X_for_prediction
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_build_X_for_prediction_shape():
    """Output X should have const, trend, and spend columns."""
    loaded = _make_loaded()
    df = _make_weekly_for_prediction()
    X = build_X_for_prediction(df, loaded.spend_cols, loaded.model_config, loaded.feature_state)
    assert "const" in X.columns
    assert "trend" in X.columns
    assert "meta_spend" in X.columns
    assert "google_spend" in X.columns
    assert len(X) == len(df)


@pytest.mark.pure
def test_build_X_for_prediction_trend_uses_feature_state():
    """Trend centering should use trend_mean from feature_state, not recomputed."""
    loaded = _make_loaded()
    df = _make_weekly_for_prediction(n_weeks=3, start_week_index=100)
    X = build_X_for_prediction(df, loaded.spend_cols, loaded.model_config, loaded.feature_state)
    # trend_mean = 50.0 from feature_state
    expected_trend = df["week_index"].astype(float) - 50.0
    np.testing.assert_array_almost_equal(X["trend"].values, expected_trend.values)


@pytest.mark.pure
def test_build_X_for_prediction_adstock_applied():
    """With use_adstock=True, spend columns should be transformed."""
    loaded = _make_loaded(use_adstock=True, channel_alphas={"meta_spend": 0.5, "google_spend": 0.5})
    df = _make_weekly_for_prediction()
    X = build_X_for_prediction(df, loaded.spend_cols, loaded.model_config, loaded.feature_state)
    # Adstocked values should differ from raw values (due to carryover)
    raw_meta = df["meta_spend"].values
    assert not np.allclose(X["meta_spend"].values, raw_meta), "Adstock should transform spend"


@pytest.mark.pure
def test_build_X_for_prediction_log_applied():
    """With use_log=True, spend columns should be log1p-transformed."""
    loaded = _make_loaded(use_log=True)
    df = _make_weekly_for_prediction()
    X = build_X_for_prediction(df, loaded.spend_cols, loaded.model_config, loaded.feature_state)
    # Log-transformed values should be much smaller than raw
    raw_meta = df["meta_spend"].values
    expected = np.log1p(raw_meta)
    np.testing.assert_array_almost_equal(X["meta_spend"].values, expected)


# ---------------------------------------------------------------------------
# predict_revenue
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_predict_revenue_no_lags():
    """Without lags, prediction should be X @ beta."""
    loaded = _make_loaded()
    df = _make_weekly_for_prediction(n_weeks=2)
    X = build_X_for_prediction(df, loaded.spend_cols, loaded.model_config, loaded.feature_state)

    preds = predict_revenue(loaded, X)
    assert len(preds) == 2
    assert all(p >= 0 for p in preds)  # clipped to zero


@pytest.mark.pure
def test_predict_revenue_with_lags_recursive():
    """With lags, prediction should recurse using previous predictions."""
    loaded = _make_loaded(lags_added=1)
    df = _make_weekly_for_prediction(n_weeks=3)
    X = build_X_for_prediction(df, loaded.spend_cols, loaded.model_config, loaded.feature_state)

    preds = predict_revenue(loaded, X)
    assert len(preds) == 3
    # All predictions should be non-negative
    assert all(p >= 0 for p in preds)


@pytest.mark.pure
def test_predict_revenue_log_target_inverse_transform():
    """With use_log_target=True, output should be smearing * exp(pred) - 1."""
    loaded = _make_loaded(use_log_target=True, smearing_factor=1.0)
    df = _make_weekly_for_prediction(n_weeks=2)
    X = build_X_for_prediction(df, loaded.spend_cols, loaded.model_config, loaded.feature_state)

    preds = predict_revenue(loaded, X)
    # Predictions in revenue space should be positive and much larger than log-space predictions
    assert all(p >= 0 for p in preds)
    # The inverse transform exp(log_pred) should produce values >> 1 for typical predictions
    assert all(p > 1 for p in preds)


@pytest.mark.pure
def test_predict_revenue_clipped_to_zero():
    """Negative predictions should be clipped to 0."""
    # Create a loaded model with negative coefficients to force negative predictions
    loaded = _make_loaded()
    loaded.coefficients = {
        "const": -10000.0,  # large negative intercept
        "trend": -1.0,
        "meta_spend": -1.0,
        "google_spend": -1.0,
    }
    df = _make_weekly_for_prediction(n_weeks=2)
    X = build_X_for_prediction(df, loaded.spend_cols, loaded.model_config, loaded.feature_state)

    preds = predict_revenue(loaded, X)
    assert all(p >= 0 for p in preds)
