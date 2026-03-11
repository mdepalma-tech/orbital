"""Tests for pipeline/adstock.py — per-channel adstock alpha selection via CV."""

import numpy as np
import pandas as pd
import pytest

from pipeline.adstock import select_adstock_alphas


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_weekly(n_weeks: int, seed: int = 0) -> tuple[pd.DataFrame, list[str]]:
    """Synthetic weekly DataFrame with two spend channels and revenue."""
    rng = np.random.default_rng(seed)
    spend_cols = ["meta_spend", "google_spend"]
    df = pd.DataFrame({
        "week_index": np.arange(n_weeks),
        "revenue": 1000 + rng.uniform(0, 200, n_weeks),
        "meta_spend": rng.uniform(50, 500, n_weeks),
        "google_spend": rng.uniform(50, 500, n_weeks),
    })
    return df, spend_cols


def _diagnostics_stub() -> dict:
    """Minimal diagnostics dict accepted by build_design_matrix."""
    return {
        "score": 0.8,
        "model_mode": "causal_full",
        "data_confidence_band": "high",
        "snapshot": {},
        "gating_reasons": [],
        "best_k": 0,
        "dominant_period": 52,
    }


# ---------------------------------------------------------------------------
# Fallback: not enough data
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_too_few_rows_returns_zero_alphas():
    """When len(df) < 2 * n_splits, fall back to alpha=0 for all channels."""
    df, spend_cols = _make_weekly(n_weeks=4)
    result = select_adstock_alphas(
        df, spend_cols, model_mode="causal_full",
        diagnostics=_diagnostics_stub(), n_splits=3,
    )
    assert set(result.keys()) == set(spend_cols)
    assert all(v == 0.0 for v in result.values())


@pytest.mark.pure
def test_exactly_at_threshold_returns_zero_alphas():
    """Boundary: len == 2 * n_splits still falls back (strict <)."""
    df, spend_cols = _make_weekly(n_weeks=6)  # 6 == 2*3
    result = select_adstock_alphas(
        df, spend_cols, model_mode="causal_full",
        diagnostics=_diagnostics_stub(), n_splits=3,
    )
    assert all(v == 0.0 for v in result.values())


# ---------------------------------------------------------------------------
# Return shape / type
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_returns_dict_keyed_by_spend_cols(weekly_data):
    df_weekly, spend_cols = weekly_data
    diag = _diagnostics_stub()
    result = select_adstock_alphas(df_weekly, spend_cols, "causal_full", diag)
    assert isinstance(result, dict)
    assert set(result.keys()) == set(spend_cols)


@pytest.mark.pure
def test_all_alphas_within_grid(weekly_data):
    """Every selected alpha must come from the default grid [0.0, ..., 0.9]."""
    df_weekly, spend_cols = weekly_data
    diag = _diagnostics_stub()
    result = select_adstock_alphas(df_weekly, spend_cols, "causal_full", diag)
    valid = {0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9}
    for col, alpha in result.items():
        assert alpha in valid, f"{col}: alpha {alpha} not in grid"


@pytest.mark.pure
def test_custom_alpha_grid_respected(weekly_data):
    """Only values from a custom grid should be returned."""
    df_weekly, spend_cols = weekly_data
    diag = _diagnostics_stub()
    custom_grid = [0.0, 0.5]
    result = select_adstock_alphas(
        df_weekly, spend_cols, "causal_full", diag, alpha_grid=custom_grid,
    )
    for col, alpha in result.items():
        assert alpha in custom_grid, f"{col}: {alpha} not in {custom_grid}"


# ---------------------------------------------------------------------------
# Correctness: high-carryover signal prefers high alpha
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_high_carryover_channel_gets_nonzero_alpha():
    """
    Construct revenue as a pure carryover function of meta_spend with alpha=0.8,
    plus noise. The selector should pick a non-zero alpha for meta_spend.
    """
    rng = np.random.default_rng(7)
    n = 60
    raw_spend = rng.uniform(100, 1000, n)

    # Apply geometric adstock with alpha=0.8 to generate revenue
    adstocked = np.empty(n)
    adstocked[0] = raw_spend[0]
    for t in range(1, n):
        adstocked[t] = raw_spend[t] + 0.8 * adstocked[t - 1]

    revenue = 500 + 2.0 * adstocked + rng.normal(0, 20, n)

    df = pd.DataFrame({
        "week_index": np.arange(n),
        "revenue": revenue,
        "meta_spend": raw_spend,
        "google_spend": rng.uniform(50, 500, n),  # unrelated channel
    })
    spend_cols = ["meta_spend", "google_spend"]
    diag = _diagnostics_stub()

    result = select_adstock_alphas(df, spend_cols, "causal_full", diag)
    assert result["meta_spend"] > 0.0, (
        f"Expected non-zero alpha for high-carryover channel, got {result['meta_spend']}"
    )


# ---------------------------------------------------------------------------
# Single channel
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_single_spend_column(weekly_data):
    """Works correctly with only one spend channel."""
    df_weekly, spend_cols = weekly_data
    single = [spend_cols[0]]
    diag = _diagnostics_stub()
    result = select_adstock_alphas(df_weekly, single, "causal_full", diag)
    assert list(result.keys()) == single
    assert result[single[0]] in {0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9}


# ---------------------------------------------------------------------------
# Grid with single value: always returns that value
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_single_value_grid_always_wins(weekly_data):
    """When alpha_grid has one element, every channel must get that alpha."""
    df_weekly, spend_cols = weekly_data
    diag = _diagnostics_stub()
    result = select_adstock_alphas(
        df_weekly, spend_cols, "causal_full", diag, alpha_grid=[0.3],
    )
    for col in spend_cols:
        assert result[col] == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_deterministic(weekly_data):
    """Two identical calls must return identical results."""
    df_weekly, spend_cols = weekly_data
    diag = _diagnostics_stub()
    r1 = select_adstock_alphas(df_weekly, spend_cols, "causal_full", diag)
    r2 = select_adstock_alphas(df_weekly, spend_cols, "causal_full", diag)
    assert r1 == r2
