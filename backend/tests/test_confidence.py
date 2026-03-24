"""Tests for pipeline/confidence.py — rule-based confidence scoring."""

import pytest
import numpy as np
import pandas as pd

from pipeline.modeling import ModelResult
from pipeline.confidence import compute_confidence


# ---------------------------------------------------------------------------
# Helper: build a minimal ModelResult with controllable fields
# ---------------------------------------------------------------------------

def _make_result(r2=0.8, adj_r2=0.78, vif_values=None, residual_std=10.0,
                  dollar_adj_r2=None):
    """Build a ModelResult with controlled fields for confidence testing."""
    np.random.seed(42)
    n = 50
    X = pd.DataFrame({"const": 1.0, "trend": np.arange(n, dtype=float), "spend": np.random.uniform(10, 100, n)})
    y = pd.Series(np.random.uniform(100, 500, n))
    predicted = y.values + np.random.normal(0, residual_std, n)
    residuals = y.values - predicted

    # confidence.py reads dollar_adj_r2 first; default to adj_r2 so tests
    # that control adj_r2 still work as expected.
    if dollar_adj_r2 is None:
        dollar_adj_r2 = adj_r2

    return ModelResult(
        model_type="ols",
        model=None,
        X=X,
        y=y,
        coefficients=pd.Series({"const": 100.0, "trend": 1.0, "spend": 5.0}),
        residuals=residuals,
        predicted=predicted,
        residual_std=residual_std,
        r2=r2,
        adj_r2=adj_r2,
        dollar_adj_r2=dollar_adj_r2,
        vif_values=vif_values or {},
    )


# ---------------------------------------------------------------------------
# Base confidence (no OOS)
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_confidence_high_good_model():
    """R2=0.8, n_obs=120, low VIF => 'high'."""
    result = _make_result(r2=0.8, vif_values={"spend": 2.5})
    assert compute_confidence(result, n_obs=120) == "high"


@pytest.mark.pure
def test_confidence_medium_low_r2():
    """adj_r2=0.6 (< 0.7 but >= 0.5) => 'medium' (when n_obs is large enough)."""
    result = _make_result(r2=0.65, adj_r2=0.6)
    assert compute_confidence(result, n_obs=120) == "medium"


@pytest.mark.pure
def test_confidence_medium_high_vif():
    """R2=0.8, VIF > 10 => 'medium'."""
    result = _make_result(r2=0.8, vif_values={"spend": 15.0})
    assert compute_confidence(result, n_obs=120) == "medium"


@pytest.mark.pure
def test_confidence_medium_borderline_obs():
    """R2=0.8, n_obs=75 (in 60-90 range) => 'medium'."""
    result = _make_result(r2=0.8, vif_values={"spend": 2.0})
    # n_obs in 60-90 downgrades to medium; then r2=0.8 >= 0.3 so no further downgrade
    # BUT n_obs < 90 and r2 >= 0.3 means the low rule doesn't fire
    assert compute_confidence(result, n_obs=75) == "medium"


@pytest.mark.pure
def test_confidence_low_very_low_r2():
    """adj_r2=0.4 (< 0.5) => 'low'."""
    result = _make_result(r2=0.45, adj_r2=0.4)
    assert compute_confidence(result, n_obs=120) == "low"


@pytest.mark.pure
def test_confidence_low_combined_obs_and_r2():
    """n_obs=40 (< 52) and adj_r2=0.6 => 'low' (both volume and fit downgrade)."""
    result = _make_result(r2=0.65, adj_r2=0.6)
    assert compute_confidence(result, n_obs=40) == "low"


@pytest.mark.pure
def test_confidence_low_severe_vif():
    """VIF > 20 => 'low' (severe collinearity)."""
    result = _make_result(r2=0.8, vif_values={"spend_a": 25.0, "spend_b": 3.0})
    assert compute_confidence(result, n_obs=120) == "low"


# ---------------------------------------------------------------------------
# OOS degradation
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_confidence_oos_ignored_when_insufficient():
    """oos_n_obs < 8 should not affect the result."""
    result = _make_result(r2=0.8, vif_values={"spend": 2.0})
    oos = {"oos_n_obs": 5, "oos_r2": -1.0}
    assert compute_confidence(result, n_obs=120, oos_metrics=oos) == "high"


@pytest.mark.pure
def test_confidence_oos_moderate_degradation_downgrades_high():
    """oos_n_obs=20, oos_r2=0.3 (< 0.4 but >= 0) should downgrade 'high' to 'medium'."""
    result = _make_result(r2=0.8, vif_values={"spend": 2.0})
    oos = {"oos_n_obs": 20, "oos_r2": 0.3}
    assert compute_confidence(result, n_obs=120, oos_metrics=oos) == "medium"


@pytest.mark.pure
def test_confidence_oos_severe_degradation():
    """oos_n_obs=20, oos_r2=-0.6 => 'low' regardless of base confidence."""
    result = _make_result(r2=0.8, vif_values={"spend": 2.0})
    oos = {"oos_n_obs": 20, "oos_r2": -0.6}
    assert compute_confidence(result, n_obs=120, oos_metrics=oos) == "low"


@pytest.mark.pure
def test_confidence_oos_negative_r2_forces_low():
    """oos_n_obs=10, oos_r2=-0.6 (< 0.0) should force 'low'."""
    result = _make_result(r2=0.8, vif_values={"spend": 2.0})
    oos = {"oos_n_obs": 10, "oos_r2": -0.6}
    assert compute_confidence(result, n_obs=120, oos_metrics=oos) == "low"
