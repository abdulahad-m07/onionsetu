# backend/app/routes/sync.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from backend.app.config.database import get_db
from backend.app.models.batch import BatchAssessment
from backend.app.models.scan import Scan, CapturedImage, Detection, GradingResult, SyncStatusEnum
from backend.app.models.user import User
from backend.app.schemas.sync import SyncBatchRequest, SyncBatchResponse
from backend.app.services.auth_service import get_current_user
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/sync", tags=["Sync"])

async def _upsert_synced_batch_assessment(db, batch_in, scan_id: str, actor_id: str) -> bool:
    """Persist an offline batch assessment when the client synced one.

    Returns True when a new row was inserted. Idempotent: existing ids are
    left untouched. Separated so both new and already-synced scans share it.
    """
    existing_batch = await db.execute(
        select(BatchAssessment).where(BatchAssessment.id == batch_in.id)
    )
    if existing_batch.scalar_one_or_none() is not None:
        return False
    db.add(BatchAssessment(
        id=batch_in.id,
        scan_id=scan_id,
        status=batch_in.status,
        final_grade=batch_in.final_grade.value,
        assessment_confidence=batch_in.assessment_confidence,
        sample_size=batch_in.sample_size,
        sample_size_estimated=batch_in.sample_size_estimated,
        images_analyzed=batch_in.images_analyzed,
        urs_percent=batch_in.urs_percent,
        assessed_onions_declared=batch_in.assessed_onions_declared,
        review_required=batch_in.review_required,
        policy_version=batch_in.policy_version,
        roboflow_model=batch_in.roboflow_model,
        assessment_model=batch_in.assessment_model,
        observations_json=batch_in.observations_json,
        issues_json=batch_in.issues_json,
        evidence_json=batch_in.evidence_json,
        calculated_at=batch_in.calculated_at or datetime.utcnow(),
    ))
    await AuditService.record_event(
        db=db,
        action="BATCH_SYNCED_OFFLINE",
        entity_type="BatchAssessment",
        entity_id=batch_in.id,
        actor_id=actor_id,
        payload={
            "batch_id": batch_in.id,
            "scan_id": scan_id,
            "final_grade": batch_in.final_grade.value,
        },
    )
    return True

@router.post("/batch", response_model=SyncBatchResponse)
async def sync_batch(
    payload: SyncBatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    synced_ids = []
    failed_ids = []

    for scan_in in payload.scans:
        try:
            async with db.begin_nested():
                # Check if scan already exists (Idempotent update/skip)
                existing_result = await db.execute(select(Scan).where(Scan.id == scan_in.id))
                existing_scan = existing_result.scalar_one_or_none()

                if existing_scan:
                    existing_scan.sync_status = SyncStatusEnum.SYNCED
                    if scan_in.batch_assessment is not None:
                        await _upsert_synced_batch_assessment(
                            db, scan_in.batch_assessment,
                            existing_scan.id, current_user.id,
                        )
                    synced_ids.append(scan_in.id)
                    continue

                # Create new Scan record
                scan = Scan(
                    id=scan_in.id,
                    lot_number=scan_in.lot_number,
                    farmer_name=scan_in.farmer_name,
                    farmer_phone=scan_in.farmer_phone,
                    procurement_center_id=scan_in.procurement_center_id,
                    grader_id=scan_in.grader_id,
                    sync_status=SyncStatusEnum.SYNCED,
                    report_url=scan_in.report_url,
                    audit_hash=scan_in.audit_hash,
                    created_at=scan_in.created_at or datetime.utcnow(),
                )
                db.add(scan)
                await db.flush()

                for img in scan_in.images:
                    db.add(CapturedImage(
                        id=img.id,
                        scan_id=scan.id,
                        local_path=img.local_path,
                        remote_storage_url=img.remote_storage_url,
                        angle=img.angle,
                        sharpness_score=img.sharpness_score,
                        brightness_score=img.brightness_score,
                        quality_passed=img.quality_passed,
                        captured_at=img.captured_at or datetime.utcnow(),
                    ))

                for det in scan_in.detections:
                    db.add(Detection(
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
                    ))

                if scan_in.result:
                    r = scan_in.result
                    db.add(GradingResult(
                        id=r.id,
                        scan_id=scan.id,
                        grade_a_percentage=r.grade_a_percentage,
                        urs_percentage=r.urs_percentage,
                        average_ai_confidence=r.average_ai_confidence,
                        confidence_status=r.confidence_status,
                        policy_version=r.policy_version,
                        total_onions_count=r.total_onions_count,
                        grade_a_count=r.grade_a_count,
                        damaged_count=r.damaged_count,
                        rotten_count=r.rotten_count,
                        sprouted_count=r.sprouted_count,
                        undersized_count=r.undersized_count,
                        avg_size_mm=r.avg_size_mm,
                        audit_hash=r.audit_hash,
                        calculated_at=r.calculated_at or datetime.utcnow(),
                    ))

                # Audit record for synced batch item
                await AuditService.record_event(
                    db=db,
                    action="SCAN_SYNCED_OFFLINE",
                    entity_type="Scan",
                    entity_id=scan.id,
                    actor_id=current_user.id,
                    payload={"lot_number": scan.lot_number, "device": payload.client_device_id},
                )

                # Persist an offline batch assessment when the client synced one.
                if scan_in.batch_assessment is not None:
                    await _upsert_synced_batch_assessment(
                        db, scan_in.batch_assessment, scan.id, current_user.id
                    )

                synced_ids.append(scan.id)
        except Exception:
            failed_ids.append(scan_in.id)

    await db.commit()

    return SyncBatchResponse(
        processed_count=len(synced_ids),
        synced_ids=synced_ids,
        failed_ids=failed_ids,
        message=f"Successfully synced {len(synced_ids)} scans from device {payload.client_device_id}.",
    )
