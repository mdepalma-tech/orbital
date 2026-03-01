"""Step 3 — Build the design matrix X and target vector y."""

from typing import Any, Dict, Optional

import pandas as pd
import numpy as np


def build_design_matrix(
    df_weekly: pd.DataFrame,
    spend_cols: list[str],
    model_mode: Optional[str] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Constructs from weekly-aggregated data:
      y = revenue
      X = intercept + trend + event dummies + spend columns

    Event dummy columns (event_*) are expected to already exist in df_weekly,
    applied at daily granularity and propagated through weekly aggregation.
    """
    X = pd.DataFrame(index=df_weekly.index)

    # Intercept
    X["const"] = 1.0

    # Trend index from weekly aggregation
    X["trend"] = df_weekly["week_index"].astype(float)

    # Event columns (pre-baked into df_weekly by apply_event_dummies + aggregation)
    event_cols = [c for c in df_weekly.columns if c.startswith("event_")]
    for col in event_cols:
        X[col] = df_weekly[col].astype(float)

    # Spend columns
    for col in spend_cols:
        X[col] = df_weekly[col].astype(float)

    y = df_weekly["revenue"].astype(float)
    y.index = X.index

    # Final sanity: no NaN
    assert X.isna().sum().sum() == 0, "Design matrix contains NaN"
    assert y.isna().sum() == 0, "Target vector contains NaN"

    return X, y
