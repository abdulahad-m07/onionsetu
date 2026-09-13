# backend/app/schemas/inference.py
from typing import List, Optional
from pydantic import BaseModel, Field
from backend.app.models.scan import DefectTypeEnum

class NormalizedPrediction(BaseModel):
    """One validated Roboflow detection in OnionSetu's internal schema.

    Coordinates are top-left pixel values in the SUBMITTED image space
    (converted from Roboflow's center-based x/y). `roboflow_class` is the
    raw model label, passed through verbatim — never fabricated.
    `defect_type` is mapped only when the raw label is a known quality
    class; otherwise UNKNOWN with `quality_mapped=False`.
    """

    x: float = Field(..., description="Top-left x in submitted-image pixels")
    y: float = Field(..., description="Top-left y in submitted-image pixels")
    width: float = Field(..., gt=0)
    height: float = Field(..., gt=0)
    roboflow_class: str
    class_id: Optional[int] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    detection_id: Optional[str] = None
    defect_type: DefectTypeEnum = DefectTypeEnum.UNKNOWN
    quality_mapped: bool = False

class InferenceAnalyzeResponse(BaseModel):
    model_id: str
    image_width: int
    image_height: int
    predictions: List[NormalizedPrediction] = []
    observed_classes: List[str] = []
    quality_classification_available: bool = False
    dropped_invalid_predictions: int = 0
