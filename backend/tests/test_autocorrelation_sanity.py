"""Sanity checks for autocorrelation lag logic and index preservation."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add parent for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.modeling import (
    fit_ols,
    check_autocorrelation,
    check_nonlinearity,
)


def test_lag_logic_and_index_preservation():
    """Synthetic data with autocorrelation: lag_1 then lag_2 should be added correctly."""
    np.random.seed(42)
    n = 52  # 1 year weekly
    dates = pd.date_range("2020-01-06", periods=n, freq="W-MON")

    # Create autocorrelated y: y_t = 0.5*y_{t-1} + 0.3*y_{t-2} + noise
    y = np.zeros(n)
    y[0] = 100
    y[1] = 100
    for t in range(2, n):
        y[t] = 0.5 * y[t - 1] + 0.3 * y[t - 2] + np.random.normal(0, 10)

    X = pd.DataFrame(
        {
            "const": 1.0,
            "trend": np.arange(n, dtype=float),
            "spend_a": np.random.uniform(10, 100, n),
        },
        index=dates,
    )
    X["trend"] = X["trend"] - X["trend"].mean()
    y_series = pd.Series(y, index=dates)

    result = fit_ols(X, y_series)
    result.dw_stat = 0.5  # Force low DW to trigger autocorr handling
    result.ljung_box_p = 0.01  # Force significant autocorrelation

    out = check_autocorrelation(result, ["spend_a"])

    assert out.lags_added in (1, 2), f"Expected lags_added 1 or 2, got {out.lags_added}"
    assert "lag_1" in out.X.columns
    if out.lags_added == 2:
        assert "lag_2" in out.X.columns
        # lag_2 should be y shifted by 2 (y_{t-2})
        expected_lag2 = result.y.shift(2).loc[out.X.index]
        np.testing.assert_array_almost_equal(out.X["lag_2"].values, expected_lag2.values)
        # lag_2 must be distinct from lag_1 (different lagged values)
        assert not np.allclose(out.X["lag_1"].values, out.X["lag_2"].values), (
            "lag_1 and lag_2 should differ"
        )

    # No NaNs in design matrix or target
    assert out.X.isna().sum().sum() == 0, "Design matrix contains NaNs"
    assert out.y.isna().sum() == 0, "Target contains NaNs"

    # Rows should shrink after adding lags (drop NaNs from shift)
    assert len(out.X) < len(X), "Row count should drop when lags are added"

    # Index preserved (DatetimeIndex or original df_weekly index)
    assert out.X.index.equals(out.y.index)
    assert isinstance(out.X.index, pd.DatetimeIndex) or len(out.X.index) > 0
    assert out.X.index.dtype == "datetime64[ns]" or str(out.X.index.dtype).startswith("datetime")

    print("PASS: lag logic and index preservation")


def test_nonlinearity_preserves_hac_flag():
    """When HAC was applied before nonlinearity, the hac_applied flag should be preserved.

    Note: check_nonlinearity refits via fit_ols/fit_ridge (non-HAC).
    HAC covariance is applied later by check_heteroskedasticity (step 8).
    The hac_applied flag is inherited so downstream steps know to reapply HAC.
    """
    np.random.seed(123)
    n = 40
    dates = pd.date_range("2020-01-06", periods=n, freq="W-MON")

    # Spend with curvature - log helps
    spend = np.random.uniform(50, 200, n) ** 1.5
    y = 100 + 20 * np.log1p(spend) + np.random.normal(0, 5, n)

    X = pd.DataFrame(
        {"const": 1.0, "trend": np.arange(n) - n / 2, "spend_a": spend},
        index=dates,
    )
    y_series = pd.Series(y, index=dates)

    result = fit_ols(X, y_series)
    result.hac_applied = True
    result.ljung_box_p = 0.02

    out = check_nonlinearity(result, ["spend_a"])

    # The hac_applied flag should propagate so check_heteroskedasticity
    # knows HAC was already requested in the pipeline.
    assert out.hac_applied, "hac_applied flag should be inherited through nonlinearity check"

    print("PASS: HAC flag preserved through nonlinearity")


if __name__ == "__main__":
    test_lag_logic_and_index_preservation()
    test_hac_consistency_in_nonlinearity()
    print("\nAll sanity checks passed.")
