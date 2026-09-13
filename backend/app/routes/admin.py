# backend/app/routes/admin.py
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from backend.app.config.database import get_db
from backend.app.models.scan import Scan, GradingResult
from backend.app.models.dispute import Dispute, DisputeStatusEnum
from backend.app.models.user import User, UserRoleEnum
from backend.app.schemas.auth import UserResponse
from backend.app.services.auth_service import require_roles

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])

@router.get("/dashboard/summary")
async def get_admin_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRoleEnum.ADMIN])),
):
    # Total Scans
    scans_count_res = await db.execute(select(func.count(Scan.id)))
    total_scans = scans_count_res.scalar_one()

    # Total Disputes
    disputes_count_res = await db.execute(select(func.count(Dispute.id)))
    total_disputes = disputes_count_res.scalar_one()

    # Pending Disputes
    pending_disputes_res = await db.execute(
        select(func.count(Dispute.id)).where(Dispute.status == DisputeStatusEnum.PENDING_REVIEW)
    )
    pending_disputes = pending_disputes_res.scalar_one()

    # Average Grade A %
    avg_grade_res = await db.execute(select(func.avg(GradingResult.grade_a_percentage)))
    avg_grade_a = avg_grade_res.scalar_one() or 0.0

    return {
        "total_scans_assessed": total_scans,
        "total_disputes_filed": total_disputes,
        "pending_disputes_review": pending_disputes,
        "overall_avg_grade_a_percentage": round(float(avg_grade_a), 2),
        "system_status": "ONLINE",
    }

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRoleEnum.ADMIN])),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()
