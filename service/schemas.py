"""Request/response contracts of the API (Pydantic). The web page and the tests rely on exactly these fields."""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

Verdict = Literal["possible", "none_seen", "unsure", "unsuitable"]
Reliability = Literal["good", "limited", "low"]
PhotoMatch = Literal["match", "partial", "mismatch", "unchecked"]


class ConditionResult(BaseModel):
    condition: str
    verdict: Verdict
    reliability: Reliability
    reasons: List[str] = Field(default_factory=list, description="language-neutral reason keys, e.g. unfamiliar, blurry")
    probability: Optional[float] = Field(None, description="calibrated score 0-1; None when the model was not run")
    threshold: Optional[float] = None
    spread: Optional[float] = Field(None, description="largest gap between slightly changed copies of the photo")
    views_positive: Optional[int] = None
    n_views: Optional[int] = None
    heatmap: Optional[str] = Field(None, description="data:image/png;base64 Grad-CAM overlay, only if requested")


class PhotoCheck(BaseModel):
    status: PhotoMatch
    tier: Optional[str] = Field(None, description="familiar | unfamiliar | very_unfamiliar | None")
    distance: Optional[float] = None
    familiar_max: Optional[float] = None
    unfamiliar_max: Optional[float] = None
    flags: List[str] = Field(default_factory=list, description="small | dark | bright | blurry | blank")
    width: int
    height: int


class SlotResult(BaseModel):
    slot: Literal["front", "crown"]
    check: PhotoCheck
    conditions: List[ConditionResult]


class PredictResponse(BaseModel):
    request_id: str
    app_version: str
    model_versions: Dict[str, str]
    phone_validated: bool
    slots: List[SlotResult]
    not_assessed: List[str]
    advice: List[str] = Field(description="language-neutral keys such as tip:dandruff, retake:dryness, multi, general")
    latency_ms: int


class ModelInfo(BaseModel):
    slot: str
    task: str
    loaded: bool
    model_version: Optional[str] = None
    classes: List[str] = Field(default_factory=list)


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    app_version: str
    phone_validated: bool
    models: List[ModelInfo]


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None
