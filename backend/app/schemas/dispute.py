# backend/app/schemas/dispute.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from backend.app.models.dispute import DisputeStatusEnum

class DisputeCreateRequest(BaseModel):
    scan_id: str
    reason: str
    evidence_urls: List[str] = []

class DisputeUpdateRequest(BaseModel):
    status: DisputeStatusEnum
    reviewer_notes: str
    revised_grade_id: Optional[str] = None

class DisputeResponse(BaseModel):
    id: str
    scan_id: str
    filed_by_user_id: str
    reason: str
    status: DisputeStatusEnum
    reviewer_notes: Optional[str] = None
    reviewer_id: Optional[str] = None
    revised_grade_id: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
