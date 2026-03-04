from pydantic import BaseModel
from typing import Any, Dict, List, Literal, Optional


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
    history_weeks: int = 8


class ForecastResponse(BaseModel):
    version_id: str
    predictions: List[float]
    last_week_index: Optional[int] = None
    spend_cols: Optional[List[str]] = None
    baseline_spend: Optional[Dict[str, float]] = None
    historical: Optional[List[Dict[str, Any]]] = None


class ForecastScenarioCreate(BaseModel):
    name: str
    last_week_index: int
    spend_cols: List[str]
    weeks: List[ForecastWeekInput]


class ForecastScenarioUpdate(BaseModel):
    name: Optional[str] = None
    weeks: Optional[List[ForecastWeekInput]] = None


class ForecastScenario(BaseModel):
    id: str
    model_version_id: str
    name: str
    last_week_index: int
    spend_cols: List[str]
    weeks: List[Dict]
    created_at: Optional[str] = None


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
