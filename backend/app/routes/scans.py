# backend/app/routes/scans.py
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from backend.app.config.database import get_db
from backend.app.models.scan import Scan, CapturedImage, Detection, GradingResult, SyncStatusEnum
from backend.app.models.user import User, UserRoleEnum
from backend.app.schemas.scan import ScanCreateRequest, ScanResponse, ScanListResponse
from backend.app.services.auth_service import get_current_user
from backend.app.services.audit_service import AuditService
from backend.app.services.report_service import ReportService
from backend.app.services.supabase_storage_service import SupabaseStorageService

router = APIRouter(prefix="/scans", tags=["Scans"])

@router.post("/", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def create_scan(
    payload: ScanCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check if scan already exists (idempotency check)
    existing_result = await db.execute(
        select(Scan)
        .options(selectinload(Scan.images), selectinload(Scan.detections), selectinload(Scan.result))
        .where(Scan.id == payload.id)
    )
    existing_scan = existing_result.scalar_one_or_none()
    if existing_scan:
        return existing_scan

    # Create new Scan record
    scan = Scan(
        id=payload.id,
        lot_number=payload.lot_number,
        farmer_name=payload.farmer_name,
        farmer_phone=payload.farmer_phone,
        procurement_center_id=payload.procurement_center_id,
        grader_id=payload.grader_id,
        sync_status=SyncStatusEnum.SYNCED,
        report_url=payload.report_url,
        audit_hash=payload.audit_hash,
        created_at=payload.created_at or datetime.utcnow(),
    )
    db.add(scan)
    await db.flush()

    # Add images
    for img in payload.images:
        img_record = CapturedImage(
            id=img.id,
            scan_id=scan.id,
            local_path=img.local_path,
            remote_storage_url=img.remote_storage_url,
            angle=img.angle,
            sharpness_score=img.sharpness_score,
            brightness_score=img.brightness_score,
            quality_passed=img.quality_passed,
            captured_at=img.captured_at or datetime.utcnow(),
        )
        db.add(img_record)

    # Add detections
    for det in payload.detections:
        det_record = Detection(
            id=det.id,
            scan_id=scan.id,
            x=det.x,
            y=det.y,
            width=det.width,
            height=det.height,
            defect_type=det.defect_type,
            confidence=det.confidence,
            estimated_diameter_mm=det.estimated_diameter_mm,
            view_angle=det.view_angle,
        )
        db.add(det_record)

    # Add grading result
    if payload.result:
        res = payload.result
        result_record = GradingResult(
            id=res.id,
            scan_id=scan.id,
            grade_a_percentage=res.grade_a_percentage,
            urs_percentage=res.urs_percentage,
            average_ai_confidence=res.average_ai_confidence,
            confidence_status=res.confidence_status,
            policy_version=res.policy_version,
            total_onions_count=res.total_onions_count,
            grade_a_count=res.grade_a_count,
            damaged_count=res.damaged_count,
            rotten_count=res.rotten_count,
            sprouted_count=res.sprouted_count,
            undersized_count=res.undersized_count,
            avg_size_mm=res.avg_size_mm,
            audit_hash=res.audit_hash,
            calculated_at=res.calculated_at or datetime.utcnow(),
        )
        db.add(result_record)
        scan.audit_hash = res.audit_hash

    # Record SHA-256 Audit Event
    await AuditService.record_event(
        db=db,
        action="SCAN_CREATED",
        entity_type="Scan",
        entity_id=scan.id,
        actor_id=current_user.id,
        payload={
            "scan_id": scan.id,
            "lot_number": scan.lot_number,
            "grade_a_percentage": payload.result.grade_a_percentage if payload.result else 0.0,
            "urs_percentage": payload.result.urs_percentage if payload.result else 0.0,
            "total_count": payload.result.total_onions_count if payload.result else 0,
        },
    )

    await db.commit()

    # Re-fetch with all eager relationships loaded
    fetch_result = await db.execute(
        select(Scan)
        .options(selectinload(Scan.images), selectinload(Scan.detections), selectinload(Scan.result))
        .where(Scan.id == scan.id)
    )
    return fetch_result.scalar_one()

@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan record not found.")
    return scan

@router.get("/", response_model=ScanListResponse)
async def list_scans(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    procurement_center_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Scan).options(
        selectinload(Scan.images), selectinload(Scan.detections), selectinload(Scan.result)
    )

    if search:
        query = query.where(
            (Scan.lot_number.ilike(f"%{search}%")) |
            (Scan.farmer_name.ilike(f"%{search}%")) |
            (Scan.farmer_phone.contains(search))
        )
    if procurement_center_id:
        query = query.where(Scan.procurement_center_id == procurement_center_id)

    # Count total
    count_query = select(func.count(Scan.id))
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Paginate
    query = query.order_by(Scan.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return ScanListResponse(total=total, page=page, page_size=page_size, items=items)

@router.post("/{scan_id}/generate-report")
async def generate_scan_report(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scan = await get_scan(scan_id=scan_id, db=db, current_user=current_user)
    scan_schema = ScanResponse.model_validate(scan)

    pdf_bytes = ReportService.generate_pdf_report(scan_schema)
    file_name = f"report_{scan.id}.pdf"
    report_url = await SupabaseStorageService.upload_pdf_report(pdf_bytes, file_name)

    scan.report_url = report_url
    await db.commit()

    return {"scan_id": scan.id, "report_url": report_url, "generated_at": datetime.utcnow().isoformat()}
