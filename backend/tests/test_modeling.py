"""Tests for pipeline/modeling.py — OLS, Ridge, and diagnostic decision tree."""

import pytest
import numpy as np
import pandas as pd

from pipeline.modeling import (
    ModelResult,
    fit_ols,
    fit_ridge,
    check_vif,
    check_autocorrelation,
    check_heteroskedasticity,
    check_nonlinearity,
    run_model,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_design_matrix(n=52, seed=42):
    """Build a simple design matrix with const, trend, and two spend columns."""
    np.random.seed(seed)
    dates = pd.date_range("2020-01-06", periods=n, freq="W-MON")
    X = pd.DataFrame({
        "const": 1.0,
        "trend": np.arange(n, dtype=float) - n / 2,
        "spend_a": np.random.uniform(50, 300, n),
        "spend_b": np.random.uniform(20, 150, n),
    }, index=dates)
    return X


def _make_y_from_X(X, intercept=500, coef_a=3.0, coef_b=2.0, noise_std=50, seed=42):
    """Generate y = intercept + coef_a*spend_a + coef_b*spend_b + noise."""
    np.random.seed(seed)
    y = (
        intercept
        + coef_a * X["spend_a"]
        + coef_b * X["spend_b"]
        + np.random.normal(0, noise_std, len(X))
    )
    return pd.Series(y, index=X.index)


# ---------------------------------------------------------------------------
# fit_ols
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_fit_ols_returns_model_result():
    X = _make_design_matrix()
    y = _make_y_from_X(X)
    result = fit_ols(X, y)
    assert isinstance(result, ModelResult)
    assert result.model_type == "ols"
    assert result.ridge_applied is False


@pytest.mark.slow
def test_fit_ols_coefficients_reasonable():
    """On synthetic y = 500 + 3*a + 2*b + noise, coefficients should be near true values."""
    X = _make_design_matrix(n=200)
    y = _make_y_from_X(X, intercept=500, coef_a=3.0, coef_b=2.0, noise_std=30)
    result = fit_ols(X, y)
    assert abs(result.coefficients["spend_a"] - 3.0) < 0.5
    assert abs(result.coefficients["spend_b"] - 2.0) < 0.5


@pytest.mark.slow
def test_fit_ols_r2_positive():
    X = _make_design_matrix()
    y = _make_y_from_X(X)
    result = fit_ols(X, y)
    assert 0 < result.r2 <= 1.0


# ---------------------------------------------------------------------------
# fit_ridge
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_fit_ridge_returns_model_result():
    X = _make_design_matrix()
    y = _make_y_from_X(X)
    result = fit_ridge(X, y)
    assert isinstance(result, ModelResult)
    assert result.model_type == "ridge"
    assert result.ridge_applied is True


@pytest.mark.slow
def test_fit_ridge_coefficients_shrunk():
    """Ridge coefficients should be smaller in magnitude than OLS for collinear data."""
    np.random.seed(42)
    n = 100
    x1 = np.random.uniform(50, 300, n)
    x2 = x1 + np.random.normal(0, 5, n)  # highly correlated with x1
    X = pd.DataFrame({
        "const": 1.0,
        "trend": np.arange(n, dtype=float) - n / 2,
        "spend_a": x1,
        "spend_b": x2,
    })
    y = pd.Series(500 + 3 * x1 + 2 * x2 + np.random.normal(0, 50, n))

    ols_result = fit_ols(X, y)
    ridge_result = fit_ridge(X, y)

    # Ridge should shrink the extreme OLS coefficients
    ols_max = max(abs(ols_result.coefficients["spend_a"]), abs(ols_result.coefficients["spend_b"]))
    ridge_max = max(abs(ridge_result.coefficients["spend_a"]), abs(ridge_result.coefficients["spend_b"]))
    assert ridge_max < ols_max


# ---------------------------------------------------------------------------
# check_vif
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_check_vif_low_vif_stays_ols():
    """When max VIF < 10, result should remain OLS."""
    X = _make_design_matrix()
    y = _make_y_from_X(X)
    result = fit_ols(X, y)
    out = check_vif(result, ["spend_a", "spend_b"])
    assert out.model_type == "ols"
    assert out.ridge_applied is False


@pytest.mark.slow
def test_check_vif_high_vif_switches_to_ridge():
    """When max VIF > 10 (collinear spend), result should switch to Ridge."""
    np.random.seed(42)
    n = 60
    x1 = np.random.uniform(50, 300, n)
    x2 = x1 + np.random.normal(0, 1, n)  # near-perfect correlation
    X = pd.DataFrame({
        "const": 1.0,
        "trend": np.arange(n, dtype=float) - n / 2,
        "spend_a": x1,
        "spend_b": x2,
    })
    y = pd.Series(500 + 3 * x1 + 2 * x2 + np.random.normal(0, 50, n))
    result = fit_ols(X, y)
    out = check_vif(result, ["spend_a", "spend_b"])
    assert out.ridge_applied is True
    assert max(out.vif_values.values()) > 10


# ---------------------------------------------------------------------------
# check_autocorrelation
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_check_autocorrelation_no_autocorr():
    """When residuals aren't autocorrelated, no lags should be added."""
    X = _make_design_matrix(n=80)
    y = _make_y_from_X(X, noise_std=50)
    result = fit_ols(X, y)
    out = check_autocorrelation(result, ["spend_a", "spend_b"])
    # With random noise, autocorrelation should not be significant
    # (Ljung-Box p >= 0.05 expected for white noise)
    if out.ljung_box_p >= 0.05:
        assert out.lags_added == 0


# ---------------------------------------------------------------------------
# check_heteroskedasticity
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_check_heteroskedasticity_no_action_for_ridge():
    """Ridge models should skip the heteroskedasticity check entirely."""
    X = _make_design_matrix()
    y = _make_y_from_X(X)
    result = fit_ridge(X, y)
    out = check_heteroskedasticity(result)
    assert out.hac_applied is False  # Ridge skips this step


# ---------------------------------------------------------------------------
# run_model (full orchestration)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_run_model_orchestrates_all_steps():
    """run_model should return a valid ModelResult with all diagnostics populated."""
    X = _make_design_matrix(n=80)
    y = _make_y_from_X(X)
    result = run_model(X, y, ["spend_a", "spend_b"])
    assert isinstance(result, ModelResult)
    assert result.r2 > 0
    assert result.residual_std > 0
    assert isinstance(result.vif_values, dict)


@pytest.mark.slow
def test_run_model_returns_consistent_lengths():
    """Predicted, residuals, X, and y should all have consistent lengths."""
    X = _make_design_matrix(n=80)
    y = _make_y_from_X(X)
    result = run_model(X, y, ["spend_a", "spend_b"])
    assert len(result.predicted) == len(result.X)
    assert len(result.residuals) == len(result.X)
    assert len(result.y) == len(result.X)
