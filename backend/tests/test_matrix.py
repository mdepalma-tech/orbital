"""Tests for pipeline/matrix.py — design matrix construction and adstock."""

import pytest
import numpy as np
import pandas as pd

from pipeline.matrix import get_model_config, geometric_adstock, build_design_matrix


# ---------------------------------------------------------------------------
# get_model_config
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_get_model_config_causal_full():
    config = get_model_config("causal_full")
    assert config["use_adstock"] is True
    assert "adstock_alpha" not in config  # per-channel alphas selected externally
    assert config["use_log"] is False
    assert config["use_log_target"] is False


@pytest.mark.pure
def test_get_model_config_causal_cautious():
    config = get_model_config("causal_cautious")
    assert config["use_adstock"] is True
    assert "adstock_alpha" not in config
    assert config["use_log"] is False
    assert config["use_log_target"] is False


@pytest.mark.pure
def test_get_model_config_diagnostic_stabilized():
    config = get_model_config("diagnostic_stabilized")
    assert config["use_adstock"] is False
    assert "adstock_alpha" not in config
    assert config["use_log"] is False
    assert config["use_log_target"] is False


@pytest.mark.pure
def test_get_model_config_none_defaults_to_stabilized():
    config = get_model_config(None)
    assert config["use_adstock"] is False


# ---------------------------------------------------------------------------
# geometric_adstock
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_geometric_adstock_formula():
    """A_t = Spend_t + alpha * A_{t-1}. For [100, 0, 0] with alpha=0.5: [100, 50, 25]."""
    series = pd.Series([100.0, 0.0, 0.0])
    result, final = geometric_adstock(series, alpha=0.5, init_value=0.0)
    np.testing.assert_array_almost_equal(result.values, [100.0, 50.0, 25.0])
    assert final == 25.0


@pytest.mark.pure
def test_geometric_adstock_with_init_value():
    """init_value seeds A_{-1}. For [0] with alpha=0.5, init=200: A_0 = 0 + 0.5*200 = 100."""
    series = pd.Series([0.0])
    result, final = geometric_adstock(series, alpha=0.5, init_value=200.0)
    assert result.iloc[0] == pytest.approx(100.0)


@pytest.mark.pure
def test_geometric_adstock_empty_series():
    """Empty input returns empty series and the init_value."""
    series = pd.Series(dtype=float)
    result, final = geometric_adstock(series, alpha=0.5, init_value=42.0)
    assert len(result) == 0
    assert final == 42.0


@pytest.mark.pure
def test_geometric_adstock_preserves_index():
    """Output should have the same index as input."""
    idx = pd.date_range("2022-01-01", periods=3, freq="W-MON")
    series = pd.Series([10.0, 20.0, 30.0], index=idx)
    result, _ = geometric_adstock(series, alpha=0.3)
    assert result.index.equals(idx)


@pytest.mark.pure
def test_geometric_adstock_returns_final_carryover():
    """Second return value should be the last element of the output."""
    series = pd.Series([100.0, 50.0, 25.0])
    result, final = geometric_adstock(series, alpha=0.5)
    assert final == result.iloc[-1]


# ---------------------------------------------------------------------------
# build_design_matrix
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_build_design_matrix_has_const_and_trend(weekly_data):
    """X should always contain 'const' and 'trend' columns."""
    df_weekly, spend_cols = weekly_data
    X, y, fs = build_design_matrix(df_weekly, spend_cols)
    assert "const" in X.columns
    assert "trend" in X.columns
    assert (X["const"] == 1.0).all()


@pytest.mark.pure
def test_build_design_matrix_trend_is_centered(weekly_data):
    """Trend column should have mean approximately 0."""
    df_weekly, spend_cols = weekly_data
    X, y, fs = build_design_matrix(df_weekly, spend_cols)
    assert abs(X["trend"].mean()) < 0.01


@pytest.mark.pure
def test_build_design_matrix_no_nan(weekly_data):
    """X and y should contain no NaN values."""
    df_weekly, spend_cols = weekly_data
    X, y, fs = build_design_matrix(df_weekly, spend_cols)
    assert X.isna().sum().sum() == 0
    assert y.isna().sum() == 0


@pytest.mark.pure
def test_build_design_matrix_raw_target_for_causal_full(weekly_data):
    """With causal_full (use_log_target=False), y should equal raw revenue."""
    df_weekly, spend_cols = weekly_data
    X, y, fs = build_design_matrix(df_weekly, spend_cols, model_mode="causal_full")
    expected_y = df_weekly["revenue"].astype(float)
    np.testing.assert_array_almost_equal(y.values, expected_y.values)


@pytest.mark.pure
def test_build_design_matrix_feature_state_trend_mean(weekly_data):
    """Returned feature_state should contain 'trend_mean'."""
    df_weekly, spend_cols = weekly_data
    X, y, fs = build_design_matrix(df_weekly, spend_cols)
    assert "trend_mean" in fs


@pytest.mark.pure
def test_build_design_matrix_feature_state_adstock_last(weekly_data):
    """With adstock enabled and channel_alphas provided, feature_state should contain 'adstock_last' dict."""
    df_weekly, spend_cols = weekly_data
    channel_alphas = {col: 0.5 for col in spend_cols}
    X, y, fs = build_design_matrix(df_weekly, spend_cols, model_mode="causal_full", channel_alphas=channel_alphas)
    assert "adstock_last" in fs
    assert isinstance(fs["adstock_last"], dict)
    for col in spend_cols:
        assert col in fs["adstock_last"]
    assert "channel_alphas" in fs
    assert fs["channel_alphas"] == channel_alphas


@pytest.mark.pure
def test_build_design_matrix_feature_state_reuse(weekly_data):
    """Passing feature_state from a prior call should produce consistent trend centering."""
    df_weekly, spend_cols = weekly_data
    _, _, fs1 = build_design_matrix(df_weekly, spend_cols, model_mode="causal_full")
    # Use feature_state from first call on a subset (simulating test split)
    subset = df_weekly.iloc[:10].copy()
    subset["week_index"] = range(len(subset))
    X2, _, _ = build_design_matrix(subset, spend_cols, model_mode="causal_full", feature_state=fs1)
    # Trend should use fs1's trend_mean, not recompute
    expected_trend = subset["week_index"].astype(float) - fs1["trend_mean"]
    np.testing.assert_array_almost_equal(X2["trend"].values, expected_trend.values)


@pytest.mark.pure
def test_build_design_matrix_includes_event_columns(weekly_data):
    """Event dummy columns from df_weekly should be carried into X."""
    df_weekly, spend_cols = weekly_data
    event_cols = [c for c in df_weekly.columns if c.startswith("event_")]
    X, y, fs = build_design_matrix(df_weekly, spend_cols)
    for col in event_cols:
        assert col in X.columns
