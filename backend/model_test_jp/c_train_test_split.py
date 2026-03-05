import pandas as pd
import numpy as np
import os
from typing import Tuple


def time_based_split(
    df: pd.DataFrame,
    train_ratio: float = 0.8,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split the DataFrame into training and holdout sets in chronological order.
    Args:
        df          : Full DataFrame sorted by date ascending.
        train_ratio : Fraction of rows used for training (default 80%).

    Returns:
        df_train : Training period — used to fit the model.
        df_test  : Holdout period — never seen during fitting, used only for evaluation.
    """
    
    split_idx = int(len(df) * train_ratio)
    df_train  = df.iloc[:split_idx].copy()
    df_test   = df.iloc[split_idx:].copy()

    print(f"\nTrain period  : {df_train['date'].min().date()} → {df_train['date'].max().date()}  ({len(df_train)} rows)")
    print(f"Holdout period: {df_test['date'].min().date()} → {df_test['date'].max().date()}  ({len(df_test)} rows)")

    return df_train, df_test