"""Tests for pipeline/counterfactual.py — incremental impact and marginal ROI."""

import pytest
import numpy as np
import pandas as pd

from pipeline.modeling import fit_ols
from pipeline.counterfactual import compute_counterfactual


# ---------------------------------------------------------------------------
# Helper: build a fitted ModelResult with known spend structure
# ---------------------------------------------------------------------------

def _make_fitted_result(n=50, seed=42):
    """Fit OLS on synthetic data where revenue is driven by spend."""
    np.random.seed(seed)
    spend_a = np.random.uniform(50, 300, n)
    spend_b = np.random.uniform(20, 150, n)
    noise = np.random.normal(0, 50, n)
    revenue = 1000 + 3.0 * spend_a + 2.0 * spend_b + noise

    X = pd.DataFrame({
        "const": 1.0,
        "trend": np.arange(n, dtype=float) - n / 2,
        "spend_a": spend_a,
        "spend_b": spend_b,
    })
    y = pd.Series(revenue)
    result = fit_ols(X, y)
    return result, ["spend_a", "spend_b"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_compute_counterfactual_returns_dict_pair():
    """Should return a tuple of two dicts."""
    result, spend_cols = _make_fitted_result()
    incremental, roi = compute_counterfactual(result, spend_cols)
    assert isinstance(incremental, dict)
    assert isinstance(roi, dict)


@pytest.mark.pure
def test_compute_counterfactual_keys_match_spend_cols():
    """Both dicts should have keys matching the spend columns."""
    result, spend_cols = _make_fitted_result()
    incremental, roi = compute_counterfactual(result, spend_cols)
    assert set(incremental.keys()) == set(spend_cols)
    assert set(roi.keys()) == set(spend_cols)


@pytest.mark.pure
def test_compute_counterfactual_positive_coefficient_positive_incremental():
    """When spend coefficient > 0, incremental impact should be > 0."""
    result, spend_cols = _make_fitted_result()
    incremental, roi = compute_counterfactual(result, spend_cols)
    # Our synthetic data has positive coefficients for both channels
    for col in spend_cols:
        if result.coefficients.get(col, 0) > 0:
            assert incremental[col] > 0, f"Expected positive incremental for {col}"


@pytest.mark.pure
def test_compute_counterfactual_roi_formula():
    """marginal_roi should equal incremental / total_spend for each channel."""
    result, spend_cols = _make_fitted_result()
    incremental, roi = compute_counterfactual(result, spend_cols)
    for col in spend_cols:
        total_spend = float(result.X[col].sum())
        if total_spend > 0:
            expected_roi = round(incremental[col] / total_spend, 4)
            assert roi[col] == expected_roi, f"ROI mismatch for {col}"


@pytest.mark.pure
def test_compute_counterfactual_zero_spend_column():
    """A channel with all-zero spend should have 0 ROI (no spend to divide by)."""
    np.random.seed(42)
    n = 50
    spend_a = np.random.uniform(50, 300, n)
    spend_b = np.zeros(n)  # zero spend from the start
    revenue = 1000 + 3.0 * spend_a + np.random.normal(0, 50, n)

    X = pd.DataFrame({
        "const": 1.0,
        "trend": np.arange(n, dtype=float) - n / 2,
        "spend_a": spend_a,
        "spend_b": spend_b,
    })
    y = pd.Series(revenue)
    result = fit_ols(X, y)

    incremental, roi = compute_counterfactual(result, ["spend_a", "spend_b"])
    # spend_b has zero total spend, so ROI should be 0
    assert roi["spend_b"] == 0.0


@pytest.mark.pure
def test_compute_counterfactual_with_log_target():
    """With use_log_target=True, inverse transform should be applied."""
    np.random.seed(42)
    n = 50
    spend = np.random.uniform(50, 300, n)
    revenue = 1000 + 3.0 * spend + np.random.normal(0, 50, n)
    y_log = np.log1p(revenue)

    X = pd.DataFrame({
        "const": 1.0,
        "trend": np.arange(n, dtype=float) - n / 2,
        "spend_a": np.log1p(spend),
    })
    y = pd.Series(y_log)
    result = fit_ols(X, y)

    incremental, roi = compute_counterfactual(
        result, ["spend_a"], use_log_target=True, smearing_factor=1.0
    )
    # With log target, incremental should still be positive (spend has positive effect)
    assert incremental["spend_a"] > 0
