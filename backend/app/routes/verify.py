# backend/app/routes/verify.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from backend.app.config.database import get_db
from backend.app.models.batch import BatchAssessment
from backend.app.models.scan import Scan
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/verify", tags=["Verification"])


class ScanVerificationResponse(BaseModel):
    """Public, non-PII verification payload backing report QR codes.

    Deliberately excludes farmer name/phone and grader identity: anyone
    scanning a printed report can confirm the grade and audit standing
    without accessing personal data.
    """

    scan_id: str
    lot_number: str
    procurement_center_id: str
    final_grade: Optional[str] = None
    assessment_confidence: Optional[float] = None
    sample_size: Optional[int] = None
    sample_size_estimated: Optional[bool] = None
    images_analyzed: Optional[int] = None
    urs_percent: Optional[float] = None
    assessed_onions_declared: Optional[int] = None
    policy_version: Optional[str] = None
    roboflow_model: Optional[str] = None
    assessment_model: Optional[str] = None
    calculated_at: Optional[datetime] = None
    audit_hash: Optional[str] = None
    chain_valid: bool
    verified_at: datetime


@router.get("/{scan_id}", response_model=ScanVerificationResponse)
async def verify_scan(scan_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scan record not found."
        )

    batch_result = await db.execute(
        select(BatchAssessment)
        .where(BatchAssessment.scan_id == scan_id)
        .order_by(BatchAssessment.calculated_at.desc())
        .limit(1)
    )
    batch_row = batch_result.scalar_one_or_none()

    chain = await AuditService.verify_chain(db)

    return ScanVerificationResponse(
        scan_id=scan.id,
        lot_number=scan.lot_number,
        procurement_center_id=scan.procurement_center_id,
        final_grade=batch_row.final_grade if batch_row else None,
        assessment_confidence=(
            batch_row.assessment_confidence if batch_row else None
        ),
        sample_size=batch_row.sample_size if batch_row else None,
        sample_size_estimated=(
            batch_row.sample_size_estimated if batch_row else None
        ),
        images_analyzed=batch_row.images_analyzed if batch_row else None,
        urs_percent=batch_row.urs_percent if batch_row else None,
        assessed_onions_declared=(
            batch_row.assessed_onions_declared if batch_row else None
        ),
        policy_version=batch_row.policy_version if batch_row else None,
        roboflow_model=batch_row.roboflow_model if batch_row else None,
        assessment_model=batch_row.assessment_model if batch_row else None,
        calculated_at=batch_row.calculated_at if batch_row else None,
        audit_hash=scan.audit_hash,
        chain_valid=bool(chain.get("is_valid", False)),
        verified_at=datetime.utcnow(),
    )
