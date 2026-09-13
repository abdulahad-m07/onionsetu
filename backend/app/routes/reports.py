# backend/app/routes/reports.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from backend.app.config.database import get_db
from backend.app.models.batch import BatchAssessment
from backend.app.models.scan import Scan
from backend.app.schemas.batch import BatchAssessmentSchema
from backend.app.schemas.scan import ScanResponse
from backend.app.services.auth_service import get_current_user
from backend.app.services.report_service import ReportService
from backend.app.models.user import User

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/{scan_id}/download")
async def download_report_pdf(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Scan)
        .options(selectinload(Scan.images), selectinload(Scan.detections), selectinload(Scan.result))
        .where(Scan.id == scan_id)
    )
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")

    scan_schema = ScanResponse.model_validate(scan)

    # Attach the latest validated batch assessment when one exists; the
    # report then represents the BATCH (one A/B/C/Reject), not one onion.
    batch_schema = None
    batch_result = await db.execute(
        select(BatchAssessment)
        .where(BatchAssessment.scan_id == scan_id)
        .order_by(BatchAssessment.calculated_at.desc())
        .limit(1)
    )
    batch_row = batch_result.scalar_one_or_none()
    if batch_row is not None:
        batch_schema = BatchAssessmentSchema.model_validate(batch_row)

    pdf_bytes = ReportService.generate_pdf_report(scan_schema, batch=batch_schema)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="onionsetu_report_{scan.lot_number}.pdf"'}
    )
