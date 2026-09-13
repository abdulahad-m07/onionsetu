# backend/app/routes/disputes.py
from datetime import datetime
from uuid import uuid4
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.config.database import get_db
from backend.app.models.dispute import Dispute, DisputeStatusEnum
from backend.app.models.scan import Scan
from backend.app.models.user import User, UserRoleEnum
from backend.app.schemas.dispute import DisputeCreateRequest, DisputeUpdateRequest, DisputeResponse
from backend.app.services.auth_service import get_current_user, require_roles
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/disputes", tags=["Disputes"])

@router.post("/", response_model=DisputeResponse, status_code=status.HTTP_201_CREATED)
async def create_dispute(
    payload: DisputeCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify scan exists
    scan_result = await db.execute(select(Scan).where(Scan.id == payload.scan_id))
    scan = scan_result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan record not found.")

    dispute = Dispute(
        id=str(uuid4()),
        scan_id=payload.scan_id,
        filed_by_user_id=current_user.id,
        reason=payload.reason,
        status=DisputeStatusEnum.PENDING_REVIEW,
        created_at=datetime.utcnow(),
    )
    db.add(dispute)

    # Record Audit event
    await AuditService.record_event(
        db=db,
        action="DISPUTE_FILED",
        entity_type="Dispute",
        entity_id=dispute.id,
        actor_id=current_user.id,
        payload={
            "dispute_id": dispute.id,
            "scan_id": dispute.scan_id,
            "reason": dispute.reason,
        },
    )

    await db.commit()
    await db.refresh(dispute)
    return dispute

@router.get("/{dispute_id}", response_model=DisputeResponse)
async def get_dispute(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Dispute).where(Dispute.id == dispute_id))
    dispute = result.scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found.")
    return dispute

@router.patch("/{dispute_id}", response_model=DisputeResponse)
async def update_dispute(
    dispute_id: str,
    payload: DisputeUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRoleEnum.GRADER, UserRoleEnum.ADMIN])),
):
    result = await db.execute(select(Dispute).where(Dispute.id == dispute_id))
    dispute = result.scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found.")

    dispute.status = payload.status
    dispute.reviewer_notes = payload.reviewer_notes
    dispute.reviewer_id = current_user.id
    dispute.revised_grade_id = payload.revised_grade_id
    dispute.resolved_at = datetime.utcnow()

    # Record Audit Event
    await AuditService.record_event(
        db=db,
        action="DISPUTE_RESOLVED",
        entity_type="Dispute",
        entity_id=dispute.id,
        actor_id=current_user.id,
        payload={
            "dispute_id": dispute.id,
            "new_status": dispute.status.value,
            "reviewer_notes": dispute.reviewer_notes,
            "revised_grade_id": dispute.revised_grade_id,
        },
    )

    await db.commit()
    await db.refresh(dispute)
    return dispute

@router.get("/", response_model=List[DisputeResponse])
async def list_disputes(
    status_filter: Optional[DisputeStatusEnum] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Dispute)
    if status_filter:
        query = query.where(Dispute.status == status_filter)
    query = query.order_by(Dispute.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()
