"""Tests for pipeline/confidence.py — rule-based confidence scoring."""

import pytest
import numpy as np
import pandas as pd

from pipeline.modeling import ModelResult
from pipeline.confidence import compute_confidence


# ---------------------------------------------------------------------------
# Helper: build a minimal ModelResult with controllable fields
# ---------------------------------------------------------------------------

def _make_result(r2=0.8, adj_r2=0.78, vif_values=None, residual_std=10.0):
    """Build a ModelResult with controlled fields for confidence testing."""
    np.random.seed(42)
    n = 50
    X = pd.DataFrame({"const": 1.0, "trend": np.arange(n, dtype=float), "spend": np.random.uniform(10, 100, n)})
    y = pd.Series(np.random.uniform(100, 500, n))
    predicted = y.values + np.random.normal(0, residual_std, n)
    residuals = y.values - predicted

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
    """R2=0.25 (< 0.3 but >= 0.15) => 'medium' (when n_obs is large enough)."""
    result = _make_result(r2=0.25)
    # n_obs=120 avoids the n_obs<90 & r2<0.3 => low rule
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
    """R2=0.10 (< 0.15) => 'low'."""
    result = _make_result(r2=0.10)
    assert compute_confidence(result, n_obs=120) == "low"


@pytest.mark.pure
def test_confidence_low_combined_obs_and_r2():
    """n_obs=80 (< 90) and R2=0.25 (< 0.3) => 'low'."""
    result = _make_result(r2=0.25)
    assert compute_confidence(result, n_obs=80) == "low"


@pytest.mark.pure
def test_confidence_low_min_vif_below_threshold():
    """min VIF < 1.01 => 'low' (indicates near-zero variation)."""
    result = _make_result(r2=0.8, vif_values={"spend_a": 1.005, "spend_b": 3.0})
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
    """oos_n_obs=20, oos_r2=-0.1 should downgrade 'high' to 'medium'."""
    result = _make_result(r2=0.8, vif_values={"spend": 2.0})
    oos = {"oos_n_obs": 20, "oos_r2": -0.1}
    assert compute_confidence(result, n_obs=120, oos_metrics=oos) == "medium"


@pytest.mark.pure
def test_confidence_oos_severe_degradation():
    """oos_n_obs=20, oos_r2=-0.6 => 'low' regardless of base confidence."""
    result = _make_result(r2=0.8, vif_values={"spend": 2.0})
    oos = {"oos_n_obs": 20, "oos_r2": -0.6}
    assert compute_confidence(result, n_obs=120, oos_metrics=oos) == "low"


@pytest.mark.pure
def test_confidence_oos_mild_degradation_small_window():
    """8 <= oos_n_obs < 16, oos_r2 < -0.5 should downgrade."""
    result = _make_result(r2=0.8, vif_values={"spend": 2.0})
    oos = {"oos_n_obs": 10, "oos_r2": -0.6}
    assert compute_confidence(result, n_obs=120, oos_metrics=oos) == "medium"


@pytest.mark.pure
def test_confidence_uses_n_obs_effective_for_volume_checks():
    """When n_obs_effective < 90 and r2 < 0.3, use effective count => 'low'.
    Original n_obs=93 would not trigger < 90, but n_obs_effective=51 (after lag drops) does."""
    result = _make_result(r2=0.25, vif_values={"spend": 2.0})
    # Without n_obs_effective: n_obs=93 -> medium (r2 < 0.3, but n >= 90)
    assert compute_confidence(result, n_obs=93) == "medium"
    # With n_obs_effective=51: effective 51 < 90 and r2 < 0.3 -> low
    assert compute_confidence(result, n_obs=93, n_obs_effective=51) == "low"
