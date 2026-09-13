# backend/app/schemas/scan.py
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from backend.app.models.scan import SyncStatusEnum, SamplingAngleEnum, DefectTypeEnum, ConfidenceGateStatusEnum
from backend.app.schemas.batch import BatchAssessmentSchema

class CapturedImageSchema(BaseModel):
    id: str
    local_path: str
    remote_storage_url: Optional[str] = None
    angle: SamplingAngleEnum = SamplingAngleEnum.TOP_VIEW
    sharpness_score: Optional[float] = None
    brightness_score: Optional[float] = None
    quality_passed: bool = True
    captured_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class DetectionSchema(BaseModel):
    id: str
    x: float
    y: float
    width: float
    height: float
    defect_type: DefectTypeEnum
    confidence: float
    estimated_diameter_mm: Optional[float] = None
    view_angle: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class GradingResultSchema(BaseModel):
    id: str
    grade_a_percentage: float
    urs_percentage: float
    average_ai_confidence: float
    confidence_status: ConfidenceGateStatusEnum = ConfidenceGateStatusEnum.HIGH_CONFIDENCE
    policy_version: str = "v1.0.0"
    total_onions_count: int
    grade_a_count: int
    damaged_count: int
    rotten_count: int
    sprouted_count: int
    undersized_count: int
    avg_size_mm: Optional[float] = None
    audit_hash: Optional[str] = None
    calculated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ScanCreateRequest(BaseModel):
    id: str
    lot_number: str
    farmer_name: str
    farmer_phone: str
    procurement_center_id: str
    grader_id: str
    sync_status: SyncStatusEnum = SyncStatusEnum.SYNCED
    images: List[CapturedImageSchema] = []
    detections: List[DetectionSchema] = []
    result: Optional[GradingResultSchema] = None
    report_url: Optional[str] = None
    audit_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    # Optional batch-level A/B/C/Reject assessment (synced when present).
    batch_assessment: Optional[BatchAssessmentSchema] = None

class ScanResponse(BaseModel):
    id: str
    lot_number: str
    farmer_name: str
    farmer_phone: str
    procurement_center_id: str
    grader_id: str
    sync_status: SyncStatusEnum
    report_url: Optional[str] = None
    audit_hash: Optional[str] = None
    created_at: datetime
    images: List[CapturedImageSchema] = []
    detections: List[DetectionSchema] = []
    result: Optional[GradingResultSchema] = None

    model_config = ConfigDict(from_attributes=True)

class ScanListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ScanResponse]
