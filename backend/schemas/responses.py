from pydantic import BaseModel
from typing import Dict, List, Literal, Optional


class ForecastWeekInput(BaseModel):
    week_index: int
    meta_spend: float = 0.0
    google_spend: float = 0.0
    tiktok_spend: float = 0.0


class ForecastRequest(BaseModel):
    version_id: Optional[str] = None
    horizon: int = 4
    spend_multiplier: float = 1.0
    weeks: Optional[List[ForecastWeekInput]] = None


class ForecastResponse(BaseModel):
    version_id: str
    predictions: List[float]


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
