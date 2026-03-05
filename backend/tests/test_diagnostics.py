"""Tests for pipeline/diagnostics.py — data quality scoring and model mode selection."""

import pytest
import numpy as np
import pandas as pd

from pipeline.diagnostics import run_diagnostics


# ---------------------------------------------------------------------------
# Helper: build weekly DataFrames with controlled properties
# ---------------------------------------------------------------------------

def _make_weekly(n_weeks=104, spend_low=50, spend_high=500, zero_share=0.0, seed=42):
    """Build a synthetic weekly DataFrame with controllable properties."""
    np.random.seed(seed)
    dates = pd.date_range("2020-01-06", periods=n_weeks, freq="W-MON")

    # Revenue with variance and seasonal structure
    revenue = 5000 + np.random.uniform(0, 2000, n_weeks) + 500 * np.sin(np.arange(n_weeks) * 2 * np.pi / 52)

    # Spend with controllable zero share
    meta_spend = np.random.uniform(spend_low, spend_high, n_weeks)
    google_spend = np.random.uniform(spend_low, spend_high, n_weeks)

    if zero_share > 0:
        n_zero = int(n_weeks * zero_share)
        zero_idx = np.random.choice(n_weeks, size=n_zero, replace=False)
        meta_spend[zero_idx] = 0.0
        google_spend[zero_idx] = 0.0

    return pd.DataFrame({
        "week_start": dates,
        "revenue": revenue.round(2),
        "orders": (revenue / 20).round(),
        "meta_spend": meta_spend.round(2),
        "google_spend": google_spend.round(2),
        "week_index": range(n_weeks),
    })


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_diagnostics_return_structure():
    df = _make_weekly(n_weeks=60)
    result = run_diagnostics(df, ["meta_spend", "google_spend"])
    assert "snapshot" in result
    assert "score" in result
    assert "model_mode" in result
    assert "data_confidence_band" in result
    assert "gating_reasons" in result


@pytest.mark.pure
def test_diagnostics_score_range():
    df = _make_weekly(n_weeks=60)
    result = run_diagnostics(df, ["meta_spend", "google_spend"])
    assert 0 <= result["score"] <= 100


# ---------------------------------------------------------------------------
# Model mode thresholds
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_diagnostics_causal_full_for_strong_data():
    """104+ weeks, high CV, good SNR should give causal_full."""
    df = _make_weekly(n_weeks=110, spend_low=50, spend_high=500)
    result = run_diagnostics(df, ["meta_spend", "google_spend"])
    # Strong data should score >= 70
    assert result["score"] >= 70
    assert result["model_mode"] == "causal_full"


@pytest.mark.pure
def test_diagnostics_diagnostic_stabilized_for_weak_data():
    """Short series with near-constant spend should give diagnostic_stabilized."""
    np.random.seed(99)
    n = 20
    dates = pd.date_range("2020-01-06", periods=n, freq="W-MON")
    df = pd.DataFrame({
        "week_start": dates,
        "revenue": np.random.uniform(100, 200, n),
        "orders": np.random.randint(5, 10, n).astype(float),
        "meta_spend": np.full(n, 100.0) + np.random.uniform(0, 1, n),  # very low CV
        "google_spend": np.full(n, 50.0) + np.random.uniform(0, 0.5, n),
        "week_index": range(n),
    })
    result = run_diagnostics(df, ["meta_spend", "google_spend"])
    assert result["model_mode"] == "diagnostic_stabilized"


@pytest.mark.pure
def test_diagnostics_low_cv_forces_stabilized():
    """Even with a high score, cv_active < 0.12 should force diagnostic_stabilized."""
    np.random.seed(42)
    n = 110
    dates = pd.date_range("2020-01-06", periods=n, freq="W-MON")
    # Nearly constant spend — CV will be very low
    df = pd.DataFrame({
        "week_start": dates,
        "revenue": 5000 + np.random.uniform(0, 2000, n) + 500 * np.sin(np.arange(n) * 2 * np.pi / 52),
        "orders": np.random.randint(100, 300, n).astype(float),
        "meta_spend": np.full(n, 200.0) + np.random.uniform(0, 2, n),  # CV ~ 0.003
        "google_spend": np.full(n, 150.0) + np.random.uniform(0, 1, n),
        "week_index": range(n),
    })
    result = run_diagnostics(df, ["meta_spend", "google_spend"])
    assert result["model_mode"] == "diagnostic_stabilized"


# ---------------------------------------------------------------------------
# Gating reasons
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_diagnostics_limited_depth_gating_reason():
    """With n_obs < 80, 'Limited historical depth' should appear in reasons."""
    df = _make_weekly(n_weeks=60)
    result = run_diagnostics(df, ["meta_spend", "google_spend"])
    assert "Limited historical depth" in result["gating_reasons"]


@pytest.mark.pure
def test_diagnostics_dropped_weekly_constant_reason():
    """Passing dropped_weekly_constant should add a gating reason."""
    df = _make_weekly(n_weeks=60)
    result = run_diagnostics(df, ["meta_spend"], dropped_weekly_constant=["tiktok_spend"])
    matching = [r for r in result["gating_reasons"] if "tiktok_spend" in r]
    assert len(matching) > 0


# ---------------------------------------------------------------------------
# Data confidence band
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_diagnostics_data_confidence_band_high():
    """Score >= 75 should give 'High' confidence band."""
    df = _make_weekly(n_weeks=110, spend_low=50, spend_high=500)
    result = run_diagnostics(df, ["meta_spend", "google_spend"])
    if result["score"] >= 75:
        assert result["data_confidence_band"] == "High"


@pytest.mark.pure
def test_diagnostics_data_confidence_band_low():
    """Score < 55 should give 'Low' confidence band."""
    np.random.seed(99)
    n = 20
    dates = pd.date_range("2020-01-06", periods=n, freq="W-MON")
    df = pd.DataFrame({
        "week_start": dates,
        "revenue": np.random.uniform(100, 200, n),
        "orders": np.random.randint(5, 10, n).astype(float),
        "meta_spend": np.full(n, 100.0) + np.random.uniform(0, 1, n),
        "google_spend": np.full(n, 50.0) + np.random.uniform(0, 0.5, n),
        "week_index": range(n),
    })
    result = run_diagnostics(df, ["meta_spend", "google_spend"])
    if result["score"] < 55:
        assert result["data_confidence_band"] == "Low"


# ---------------------------------------------------------------------------
# Snapshot sanity
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_diagnostics_snapshot_values_are_finite():
    """All snapshot values should be finite floats (no NaN or Inf)."""
    df = _make_weekly(n_weeks=60)
    result = run_diagnostics(df, ["meta_spend", "google_spend"])
    for key, val in result["snapshot"].items():
        assert np.isfinite(val), f"snapshot['{key}'] is not finite: {val}"


@pytest.mark.pure
def test_diagnostics_single_spend_column_max_corr_zero():
    """With one spend column, max_pairwise_corr should be 0.0."""
    df = _make_weekly(n_weeks=60)
    result = run_diagnostics(df, ["meta_spend"])
    assert result["snapshot"]["max_pairwise_corr"] == 0.0
