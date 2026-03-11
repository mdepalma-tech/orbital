"""Tests for pipeline/anomalies.py — residual anomaly detection via z-score."""

import pytest
import numpy as np
import pandas as pd

from pipeline.modeling import ModelResult
from pipeline.anomalies import detect_anomalies, Z_THRESHOLD


# ---------------------------------------------------------------------------
# Helper: build a ModelResult with controlled residuals
# ---------------------------------------------------------------------------

def _make_result_with_residuals(residuals, residual_std=None):
    """Build a minimal ModelResult with known residuals for anomaly testing."""
    n = len(residuals)
    residuals = np.array(residuals, dtype=float)
    if residual_std is None:
        residual_std = float(np.std(residuals, ddof=1)) if n > 1 else 0.0
    predicted = np.full(n, 100.0)
    actual = predicted + residuals

    X = pd.DataFrame({"const": np.ones(n)})
    y = pd.Series(actual)

    return ModelResult(
        model_type="ols",
        model=None,
        X=X,
        y=y,
        coefficients=pd.Series({"const": 100.0}),
        residuals=residuals,
        predicted=predicted,
        residual_std=residual_std,
        r2=0.8,
        adj_r2=0.78,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_detect_anomalies_no_anomalies_normal_residuals():
    """When all z-scores are within [-2.5, 2.5], returns empty list."""
    np.random.seed(42)
    residuals = np.random.normal(0, 10, 50)  # normal, very unlikely to exceed 2.5 std
    # Clip to guarantee no anomalies
    residuals = np.clip(residuals, -20, 20)
    result = _make_result_with_residuals(residuals)
    dates = pd.Series(pd.date_range("2022-01-01", periods=50, freq="W-MON"))
    anomalies = detect_anomalies(result, dates)
    # With clipped normal data, should have few or no anomalies
    for a in anomalies:
        assert abs(a["z_score"]) > Z_THRESHOLD


@pytest.mark.pure
def test_detect_anomalies_flags_large_residual():
    """A residual with |z| > 2.5 should produce an entry."""
    residuals = np.zeros(20)
    residuals[5] = 100.0  # large positive outlier
    result = _make_result_with_residuals(residuals)
    dates = pd.Series(pd.date_range("2022-01-01", periods=20, freq="W-MON"))
    anomalies = detect_anomalies(result, dates)
    assert len(anomalies) >= 1
    # The anomaly should correspond to index 5
    z_scores = [a["z_score"] for a in anomalies]
    assert any(z > Z_THRESHOLD for z in z_scores)


@pytest.mark.pure
def test_detect_anomalies_direction_positive():
    """Positive z-score gets direction='positive'."""
    residuals = np.zeros(20)
    residuals[0] = 100.0  # large positive
    result = _make_result_with_residuals(residuals)
    dates = pd.Series(pd.date_range("2022-01-01", periods=20, freq="W-MON"))
    anomalies = detect_anomalies(result, dates)
    positive_anomalies = [a for a in anomalies if a["z_score"] > 0]
    assert len(positive_anomalies) > 0
    assert positive_anomalies[0]["direction"] == "positive"


@pytest.mark.pure
def test_detect_anomalies_direction_negative():
    """Negative z-score gets direction='negative'."""
    residuals = np.zeros(20)
    residuals[0] = -100.0  # large negative
    result = _make_result_with_residuals(residuals)
    dates = pd.Series(pd.date_range("2022-01-01", periods=20, freq="W-MON"))
    anomalies = detect_anomalies(result, dates)
    negative_anomalies = [a for a in anomalies if a["z_score"] < 0]
    assert len(negative_anomalies) > 0
    assert negative_anomalies[0]["direction"] == "negative"


@pytest.mark.pure
def test_detect_anomalies_zero_std_returns_empty():
    """When residual_std == 0, should return empty list (no division by zero)."""
    residuals = np.zeros(10)
    result = _make_result_with_residuals(residuals, residual_std=0.0)
    dates = pd.Series(pd.date_range("2022-01-01", periods=10, freq="W-MON"))
    anomalies = detect_anomalies(result, dates)
    assert anomalies == []


@pytest.mark.pure
def test_detect_anomalies_output_structure():
    """Each anomaly dict should have the expected keys."""
    residuals = np.zeros(20)
    residuals[3] = 200.0
    result = _make_result_with_residuals(residuals)
    dates = pd.Series(pd.date_range("2022-01-01", periods=20, freq="W-MON"))
    anomalies = detect_anomalies(result, dates)
    assert len(anomalies) > 0
    expected_keys = {"ts", "actual", "predicted", "residual", "z_score", "direction"}
    assert set(anomalies[0].keys()) == expected_keys


@pytest.mark.pure
def test_detect_anomalies_date_alignment():
    """Anomaly 'ts' should match the correct date from the dates Series."""
    residuals = np.zeros(20)
    residuals[5] = 200.0
    result = _make_result_with_residuals(residuals)
    dates = pd.Series(pd.date_range("2022-01-01", periods=20, freq="W-MON"))
    anomalies = detect_anomalies(result, dates)
    # The anomaly at index 5 should have the date at position 5
    assert len(anomalies) > 0
    expected_date = str(dates.iloc[5].date())
    anomaly_dates = [a["ts"] for a in anomalies]
    assert expected_date in anomaly_dates
