"""Step 2 — Data integrity gate: continuous index, fills, variance checks."""

import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

EPSILON = 1e-6

SPEND_COLUMNS = ["meta_spend", "google_spend", "tiktok_spend"]


def _normalize_date(series: pd.Series) -> pd.Series:
    """Force a column to timezone-naive, date-only (midnight) timestamps."""
    out = pd.to_datetime(series, utc=True).dt.tz_localize(None)
    return out.dt.normalize()


def validate_and_prepare(
    timeseries: pd.DataFrame,
    spend: pd.DataFrame,
    events: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """
    Returns:
        daily  — merged DataFrame with continuous daily index
        events — cleaned events DataFrame
        spend_cols — list of spend column names with nonzero variance
    """
    if len(timeseries) < 60:
        raise ValueError(
            f"Insufficient data: {len(timeseries)} observations (minimum 60)"
        )

    # ── Normalize all timestamps to date-only at the ingestion boundary ──
    timeseries["ts"] = _normalize_date(timeseries["ts"])
    timeseries["revenue"] = timeseries["revenue"].astype(float)
    timeseries["orders"] = timeseries["orders"].astype(float)

    if timeseries["revenue"].sum() == 0:
        raise ValueError("All revenue values are zero")

    # Continuous daily date index
    date_min = timeseries["ts"].min()
    date_max = timeseries["ts"].max()
    full_dates = pd.date_range(start=date_min, end=date_max, freq="D")

    daily = timeseries.set_index("ts").reindex(full_dates)
    daily.index.name = "ts"
    daily["revenue"] = daily["revenue"].fillna(0.0)
    daily["orders"] = daily["orders"].fillna(0.0)

    # Merge spend
    present_spend_cols: list[str] = []
    if not spend.empty:
        spend["ts"] = _normalize_date(spend["ts"])

        # Guard: log if spend starts later than timeseries
        spend_min = spend["ts"].min()
        if spend_min > date_min:
            gap_days = (spend_min - date_min).days
            logger.warning(
                "Spend data starts %d day(s) after timeseries "
                "(%s vs %s). Early period will have spend=0, "
                "which weakens coefficient estimates for those days.",
                gap_days,
                spend_min.date(),
                date_min.date(),
            )

        spend_indexed = spend.set_index("ts").reindex(full_dates)
        for col in SPEND_COLUMNS:
            if col in spend_indexed.columns:
                spend_indexed[col] = spend_indexed[col].fillna(0.0).astype(float)
                daily[col] = spend_indexed[col]
                present_spend_cols.append(col)

    for col in SPEND_COLUMNS:
        if col not in daily.columns:
            daily[col] = 0.0

    # Check total spend
    all_spend = daily[present_spend_cols].sum().sum() if present_spend_cols else 0.0
    if all_spend == 0:
        raise ValueError("All spend values are zero")

    # Validate target variance
    if daily["revenue"].std() < EPSILON:
        raise ValueError("Revenue has near-zero variance — cannot model")

    # Remove zero-variance spend columns
    valid_spend_cols = [
        col
        for col in present_spend_cols
        if daily[col].std() > EPSILON
    ]

    if not valid_spend_cols:
        raise ValueError("All spend channels have zero variance")

    # Clean events — normalize to date-only
    if not events.empty:
        events["start_ts"] = _normalize_date(events["start_ts"])
        events["end_ts"] = pd.to_datetime(
            events["end_ts"], errors="coerce", utc=True
        ).dt.tz_localize(None).dt.normalize()

    daily = daily.reset_index()
    return daily, events, valid_spend_cols
