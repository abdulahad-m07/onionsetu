# backend/app/schemas/audit.py
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class AuditLogSchema(BaseModel):
    id: str
    sequence_number: Optional[int] = None
    action: str
    entity_type: str
    entity_id: str
    actor_id: str
    payload_json: str
    prev_hash: str
    current_hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AuditVerifyResponse(BaseModel):
    is_valid: bool
    total_records_checked: int
    corrupted_sequence_number: Optional[int] = None
    message: str
