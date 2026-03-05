"""Tests for pipeline/fetch.py — data ingestion from Supabase (mocked)."""

import pytest
from unittest.mock import MagicMock

from pipeline.fetch import fetch_project_data


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.mocked
def test_fetch_project_data_returns_three_dataframes(mock_supabase):
    """Should return a tuple of 3 DataFrames."""
    mock_table = mock_supabase.table.return_value

    # fetch_project_data makes 4 .execute() calls (all go through the same mock):
    # 1. projects check (.single().execute())
    # 2. timeseries
    # 3. spend
    # 4. events
    mock_table.execute.side_effect = [
        MagicMock(data={"id": "proj-123"}),
        MagicMock(data=[
            {"ts": "2022-01-01", "revenue": 100.0, "orders": 5},
            {"ts": "2022-01-02", "revenue": 200.0, "orders": 10},
        ]),
        MagicMock(data=[
            {"ts": "2022-01-01", "meta_spend": 50.0, "google_spend": 30.0, "tiktok_spend": 20.0},
        ]),
        MagicMock(data=[
            {"event_name": "Launch", "event_type": "step", "start_ts": "2022-02-01", "end_ts": None},
        ]),
    ]

    ts, spend, events = fetch_project_data("proj-123")
    assert len(ts) == 2
    assert len(spend) == 1
    assert len(events) == 1


@pytest.mark.mocked
def test_fetch_project_not_found_raises(mock_supabase):
    """Should raise ValueError when project doesn't exist."""
    mock_table = mock_supabase.table.return_value
    mock_table.execute.return_value = MagicMock(data=None)

    with pytest.raises(ValueError, match="not found"):
        fetch_project_data("nonexistent-id")


@pytest.mark.mocked
def test_fetch_calls_correct_tables(mock_supabase):
    """Should query the correct Supabase tables."""
    mock_table = mock_supabase.table.return_value
    mock_table.execute.side_effect = [
        MagicMock(data={"id": "proj-123"}),
        MagicMock(data=[]),
        MagicMock(data=[]),
        MagicMock(data=[]),
    ]

    fetch_project_data("proj-123")

    table_calls = [call.args[0] for call in mock_supabase.table.call_args_list]
    assert "projects" in table_calls
    assert "project_timeseries" in table_calls
    assert "project_spend" in table_calls
    assert "project_events" in table_calls
