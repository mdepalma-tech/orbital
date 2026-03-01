"""Step 2.75 — Deterministic weekly aggregation of validated daily data."""

import pandas as pd


def apply_event_dummies(
    df: pd.DataFrame,
    events: pd.DataFrame,
    date_col: str = "ts",
) -> pd.DataFrame:
    """Apply event dummy columns to a daily DataFrame before weekly aggregation.

    Step and pulse flags are created at daily granularity so the weekly
    aggregation can propagate them via ``max``.
    """
    if events.empty:
        return df

    df = df.copy()
    for _, event in events.iterrows():
        name = str(event["event_name"]).strip()
        col_name = f"event_{name.lower().replace(' ', '_')}"
        start = event["start_ts"]
        end = event.get("end_ts")

        if event["event_type"] == "step":
            df[col_name] = (df[date_col] >= start).astype(float)
        else:
            if pd.notna(end):
                df[col_name] = (
                    (df[date_col] >= start) & (df[date_col] <= end)
                ).astype(float)
            else:
                df[col_name] = (df[date_col] == start).astype(float)

    return df


def aggregate_to_weekly(
    df_daily: pd.DataFrame,
    spend_cols: list[str],
    date_col: str = "ts",
) -> pd.DataFrame:
    """
    Aggregates validated daily dataframe to weekly frequency.

    Assumes df_daily has:
        - date_col (default 'ts')
        - 'revenue'
        - 'orders'
        - spend columns (passed explicitly)
        - event flags (optional, created by apply_event_dummies)

    Returns a DataFrame with columns:
        week_start, revenue, orders, <spend_cols>, <event_cols>, week_index
    """
    df = df_daily.copy()
    df[date_col] = pd.to_datetime(df[date_col])

    event_cols = [c for c in df.columns if c.startswith("event_")]

    agg_dict: dict = {
        "revenue": "sum",
        "orders": "sum",
    }

    for col in spend_cols:
        agg_dict[col] = "sum"

    for col in event_cols:
        agg_dict[col] = "max"

    df_weekly = (
        df
        .groupby(pd.Grouper(key=date_col, freq="W-MON"))
        .agg(agg_dict)
        .reset_index()
    )

    df_weekly = df_weekly.rename(columns={date_col: "week_start"})
    df_weekly["week_index"] = range(len(df_weekly))

    # Drop first week if partial (< 7 days) to improve diagnostics stability.
    # Partial first week distorts CV, spend sums, and SNR.
    if len(df_weekly) > 1:
        first_week_start = df_weekly["week_start"].iloc[0]
        first_week_end = first_week_start + pd.Timedelta(days=6)
        days_in_first_week = (
            (df[date_col] >= first_week_start) & (df[date_col] <= first_week_end)
        ).sum()
        if days_in_first_week < 7:
            df_weekly = df_weekly.iloc[1:].reset_index(drop=True)
            df_weekly["week_index"] = range(len(df_weekly))

    return df_weekly
