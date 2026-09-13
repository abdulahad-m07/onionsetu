# backend/app/routes/audit.py
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.config.database import get_db
from backend.app.models.audit import AuditLog
from backend.app.models.user import User, UserRoleEnum
from backend.app.schemas.audit import AuditLogSchema, AuditVerifyResponse
from backend.app.services.auth_service import get_current_user, require_roles
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["Audit & Integrity"])

@router.get("/verify", response_model=AuditVerifyResponse)
async def verify_audit_chain(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await AuditService.verify_chain(db)
    return AuditVerifyResponse(**result)

@router.get("/logs", response_model=List[AuditLogSchema])
async def list_audit_logs(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRoleEnum.ADMIN, UserRoleEnum.GRADER])),
):
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.sequence_number.desc()).limit(limit)
    )
    return result.scalars().all()
