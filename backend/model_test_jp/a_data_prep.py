import pandas as pd
import numpy as np
import os


# ============================================================================
# DATA LOADING
# ============================================================================

def _load_local_series() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load local CSVs: sales, google, meta, tiktok."""
    BASE_DIR = os.path.dirname(__file__)

    df_sales  = pd.read_csv(os.path.join(BASE_DIR, "test_kaggle_data", "sales_data.csv"))
    df_google = pd.read_csv(os.path.join(BASE_DIR, "test_kaggle_data", "google_data.csv"))
    df_meta   = pd.read_csv(os.path.join(BASE_DIR, "test_kaggle_data", "meta_data.csv"))
    df_tiktok = pd.read_csv(os.path.join(BASE_DIR, "test_kaggle_data", "tiktok_data.csv"))

    return df_sales, df_google, df_meta, df_tiktok


def load_from_supabase(project_id: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load sales and spend from a Supabase project (aggregated to weekly). Same format as _load_local_series."""
    from pipeline.fetch import fetch_project_data
    from pipeline.validate import validate_and_prepare
    from pipeline.aggregate import apply_event_dummies, aggregate_to_weekly

    timeseries, spend, events = fetch_project_data(project_id)
    daily, events_clean, spend_cols = validate_and_prepare(timeseries, spend, events)
    daily = apply_event_dummies(daily, events_clean)
    df_weekly = aggregate_to_weekly(daily, spend_cols)

    for col in ["meta_spend", "google_spend", "tiktok_spend"]:
        if col not in df_weekly.columns:
            df_weekly[col] = 0.0

    week_start = df_weekly["week_start"].dt.strftime("%Y-%m-%d")

    df_sales = pd.DataFrame({
        "timestamp": week_start,
        "sales": df_weekly["revenue"].values,
    })
    df_google = pd.DataFrame({
        "date": week_start,
        "spend": df_weekly["google_spend"].values,
        "campaign": "search",
    })
    df_meta = pd.DataFrame({
        "date": week_start,
        "spend": df_weekly["meta_spend"].values,
    })
    df_tiktok = pd.DataFrame({
        "date": week_start,
        "spend": df_weekly["tiktok_spend"].values,
    })

    return df_sales, df_google, df_meta, df_tiktok


# ============================================================================
# DATA CLEANING
# ============================================================================

def _clean_data(
    df_sales, df_google, df_meta, df_tiktok
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Rename spend columns, timestamp → date, drop campaign column from google."""
    df_sales.rename(columns={"timestamp": "date"}, inplace=True)
    df_google.rename(columns={"spend": "google_spend"}, inplace=True)
    df_meta.rename(columns={"spend": "meta_spend"}, inplace=True)
    df_tiktok.rename(columns={"spend": "tiktok_spend"}, inplace=True)
    df_google.drop(columns=["campaign"], inplace=True)

    return df_sales, df_google, df_meta, df_tiktok

# ============================================================================
# MERGING
# ============================================================================

def _merge_data(df_sales, df_google, df_meta, df_tiktok) -> pd.DataFrame:
    """Join all dataframes on date. Replace NA with 0 if found."""
    for df in [df_sales, df_google, df_meta, df_tiktok]:
        df["date"] = pd.to_datetime(df["date"])

    df_joined = (
        df_sales
        .merge(df_google, on="date", how="inner")
        .merge(df_meta,   on="date", how="inner")
        .merge(df_tiktok, on="date", how="inner")
    )
    print(f"\nRows after join: {len(df_joined)}")

    na_counts = df_joined.isna().sum()
    if na_counts.sum() > 0:
        print("\n NA values detected:")
        print(na_counts[na_counts > 0])
        print("\n Replacing NA with 0...")
        df_joined = df_joined.fillna(0)
    else:
        print("\n✅ No NA values found.")

    return df_joined