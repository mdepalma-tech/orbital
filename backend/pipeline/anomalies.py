"""Step 11 — Residual anomaly detection via z-score."""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd
from pipeline.modeling import ModelResult

Z_THRESHOLD = 2.5


def detect_anomalies(
    result: ModelResult, dates: pd.Series
) -> List[Dict]:
    """
    Flag days where |z_score| > 2.5.
    Returns list of anomaly dicts.
    """
    residuals = result.residuals
    std = result.residual_std
    if std == 0:
        return []

    z_scores = residuals / std
    actual = result.y.values
    predicted = result.predicted

    # Align dates to result length (may be shorter if lags were added)
    n = len(residuals)
    aligned_dates = dates.iloc[-n:].reset_index(drop=True)

    anomalies: List[Dict] = []
    for i in range(n):
        z = float(z_scores[i])
        if abs(z) > Z_THRESHOLD:
            anomalies.append(
                {
                    "ts": str(aligned_dates.iloc[i].date()),
                    "actual": round(float(actual[i]), 2),
                    "predicted": round(float(predicted[i]), 2),
                    "residual": round(float(residuals[i]), 2),
                    "z_score": round(z, 4),
                    "direction": "positive" if z > 0 else "negative",
                }
            )

    return anomalies
