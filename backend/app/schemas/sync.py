# backend/app/schemas/sync.py
from typing import List
from pydantic import BaseModel
from backend.app.schemas.scan import ScanCreateRequest

class SyncBatchRequest(BaseModel):
    client_device_id: str
    scans: List[ScanCreateRequest] = []

class SyncBatchResponse(BaseModel):
    processed_count: int
    synced_ids: List[str]
    failed_ids: List[str] = []
    message: str = "Sync batch processed successfully."
