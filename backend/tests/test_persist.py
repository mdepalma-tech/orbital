"""Tests for pipeline/persist.py — Supabase persistence (mocked)."""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, call

from pipeline.modeling import ModelResult
from pipeline.persist import persist_results, _to_native


# ---------------------------------------------------------------------------
# Helper: build a minimal ModelResult for persist testing
# ---------------------------------------------------------------------------

def _make_result_for_persist():
    n = 20
    X = pd.DataFrame({
        "const": np.ones(n),
        "trend": np.arange(n, dtype=float),
        "meta_spend": np.random.uniform(50, 200, n),
    })
    y = pd.Series(np.random.uniform(100, 500, n))
    predicted = y.values + np.random.normal(0, 10, n)
    residuals = y.values - predicted

    return ModelResult(
        model_type="ols",
        model=MagicMock(
            pvalues=pd.Series({"const": 0.001, "trend": 0.05, "meta_spend": 0.01}),
            bse=pd.Series({"const": 10.0, "trend": 0.5, "meta_spend": 1.0}),
        ),
        X=X,
        y=y,
        coefficients=pd.Series({"const": 100.0, "trend": 1.5, "meta_spend": 3.2}),
        residuals=residuals,
        predicted=predicted,
        residual_std=float(np.std(residuals, ddof=1)),
        r2=0.85,
        adj_r2=0.83,
        vif_values={"meta_spend": 2.5},
        dw_stat=1.8,
        ljung_box_p=0.15,
        breusch_pagan_p=0.30,
    )


# ---------------------------------------------------------------------------
# _to_native tests
# ---------------------------------------------------------------------------

@pytest.mark.pure
def test_to_native_converts_numpy_float():
    assert type(_to_native(np.float64(3.14))) is float


@pytest.mark.pure
def test_to_native_converts_numpy_int():
    assert type(_to_native(np.int64(42))) is int


@pytest.mark.pure
def test_to_native_converts_nested_dict():
    data = {"a": np.float64(1.0), "b": [np.int64(2), np.float64(3.0)]}
    result = _to_native(data)
    assert type(result["a"]) is float
    assert type(result["b"][0]) is int
    assert type(result["b"][1]) is float


@pytest.mark.pure
def test_to_native_passes_through_native_types():
    assert _to_native("hello") == "hello"
    assert _to_native(42) == 42
    assert _to_native(3.14) == 3.14


# ---------------------------------------------------------------------------
# persist_results (mocked Supabase)
# ---------------------------------------------------------------------------

@pytest.mark.mocked
def test_persist_creates_model_if_not_exists(mock_supabase):
    """When no existing model, should insert into 'models' table."""
    np.random.seed(42)
    mock_table = mock_supabase.table.return_value
    # First query: no existing model
    mock_table.execute.return_value = MagicMock(data=[])

    result = _make_result_for_persist()
    version_id = persist_results(
        project_id="proj-123",
        result=result,
        spend_cols=["meta_spend"],
        incremental={"meta_spend": 5000.0},
        marginal_roi={"meta_spend": 2.5},
        anomalies=[],
        confidence_level="high",
        n_obs=80,
    )

    assert isinstance(version_id, str)
    # Check that insert was called on 'models' table
    table_calls = [c.args[0] for c in mock_supabase.table.call_args_list]
    assert "models" in table_calls


@pytest.mark.mocked
def test_persist_inserts_version_row(mock_supabase):
    """Should insert into 'model_versions' table."""
    np.random.seed(42)
    mock_table = mock_supabase.table.return_value
    mock_table.execute.return_value = MagicMock(data=[])

    result = _make_result_for_persist()
    persist_results(
        project_id="proj-123",
        result=result,
        spend_cols=["meta_spend"],
        incremental={"meta_spend": 5000.0},
        marginal_roi={"meta_spend": 2.5},
        anomalies=[],
        confidence_level="high",
        n_obs=80,
    )

    table_calls = [c.args[0] for c in mock_supabase.table.call_args_list]
    assert "model_versions" in table_calls


@pytest.mark.mocked
def test_persist_returns_version_id(mock_supabase):
    """Should return a string UUID."""
    np.random.seed(42)
    mock_table = mock_supabase.table.return_value
    mock_table.execute.return_value = MagicMock(data=[])

    result = _make_result_for_persist()
    version_id = persist_results(
        project_id="proj-123",
        result=result,
        spend_cols=["meta_spend"],
        incremental={"meta_spend": 5000.0},
        marginal_roi={"meta_spend": 2.5},
        anomalies=[],
        confidence_level="high",
        n_obs=80,
    )

    assert isinstance(version_id, str)
    assert len(version_id) == 36  # UUID format: 8-4-4-4-12
