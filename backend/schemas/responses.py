from pydantic import BaseModel
from typing import Dict, Literal


class RunModelResponse(BaseModel):
    model_type: Literal["ols", "ridge"]
    lags_added: int
    log_transform: bool
    hac_applied: bool
    r2: float
    adjusted_r2: float
    confidence_level: Literal["high", "medium", "low"]
    incremental_impact: Dict[str, float]
    marginal_roi: Dict[str, float]
    anomaly_count: int
