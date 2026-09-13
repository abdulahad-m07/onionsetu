# backend/app/routes/batch.py
import json
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.config.database import get_db
from backend.app.config.settings import settings
from backend.app.models.batch import BatchAssessment
from backend.app.models.scan import Scan
from backend.app.models.user import User
from backend.app.schemas.batch import (
    BatchAssessResponse,
    RoboflowImageEvidence,
)
from backend.app.services.audit_service import AuditService
from backend.app.services.auth_service import get_current_user
from backend.app.services.batch_policy import (
    BatchGradingPolicy,
    compute_urs_percent,
)
from backend.app.services.openrouter_service import (
    OpenRouterAuthError,
    OpenRouterConfigError,
    OpenRouterError,
    OpenRouterService,
    OpenRouterTimeoutError,
    MAX_UPLOAD_BYTES,
)
from backend.app.services.roboflow_service import (
    RoboflowAuthError,
    RoboflowConfigError,
    RoboflowError,
    RoboflowService,
    RoboflowTimeoutError,
)

router = APIRouter(prefix="/inference", tags=["AI Inference"])


def _map_provider_error(exc: Exception) -> HTTPException:
    """Map typed adapter errors to truthful HTTP statuses (never fake data).

    Upstream quota exhaustion (429) passes through as 429 so clients fail
    fast instead of retrying into a depleted quota.
    """
    if isinstance(exc, (RoboflowConfigError, OpenRouterConfigError)):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    if isinstance(exc, (RoboflowAuthError, OpenRouterAuthError)):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        )
    if isinstance(exc, (RoboflowTimeoutError, OpenRouterTimeoutError)):
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)
        )
    if getattr(exc, "upstream_status", None) == 429:
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
    )


def _evidence_summary(
    evidence: List[RoboflowImageEvidence],
    total: int,
    mean_conf: Optional[float],
    declared_assessed: Optional[int] = None,
) -> str:
    """Build the Roboflow evidence text handed to the assessment provider.

    All views depict the SAME physical batch: per-view detection tallies are
    reported per image and are explicitly NOT unique-onion counts (the same
    physical onions recur across views — summing them would double-count).
    The grader-declared batch size is the only valid assessment denominator.
    """
    lines = [
        f"Images with successful detection: "
        f"{sum(1 for e in evidence if e.error is None)}/{len(evidence)}.",
        f"View detections across all views (NOT unique onions — the same "
        f"physical onions may appear in multiple views; do NOT sum these as "
        f"a batch count): {total}.",
    ]
    if declared_assessed is not None:
        lines.append(
            f"Grader-declared physical batch size: {declared_assessed} "
            f"onions. Use this declared size as the assessment denominator "
            f"context; report honest URS counts against it."
        )
    if mean_conf is not None:
        lines.append(f"Mean Roboflow detection confidence: {mean_conf:.3f}.")
    for e in evidence:
        if e.error is not None:
            lines.append(f"Image {e.image_index + 1}: detection FAILED ({e.error}).")
        else:
            lines.append(
                f"Image {e.image_index + 1}: {e.detection_count} view "
                f"detection(s) [same-batch view, not new onions], "
                f"mean confidence "
                f"{e.mean_confidence if e.mean_confidence is not None else 'n/a'}, "
                f"classes: {', '.join(e.observed_classes) or 'none'}."
            )
    return "\n".join(lines)


@router.post("/batch-assess", response_model=BatchAssessResponse)
async def batch_assess(
    images: List[UploadFile] = File(...),
    scan_id: Optional[str] = Form(None),
    assessed_onions: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one batch image is required.",
        )
    # The grader-declared physical batch size (100-200 onions) is the ONLY
    # URS% denominator. It is required and preserved exactly — never derived
    # from per-view detections (summing views would double-count the same
    # physical onions).
    if assessed_onions is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="assessed_onions (grader-declared batch size, "
            f"{settings.BATCH_MIN_ASSESSED_ONIONS}-"
            f"{settings.BATCH_MAX_ASSESSED_ONIONS}) is required.",
        )
    if not (
        settings.BATCH_MIN_ASSESSED_ONIONS
        <= assessed_onions
        <= settings.BATCH_MAX_ASSESSED_ONIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="assessed_onions must be between "
            f"{settings.BATCH_MIN_ASSESSED_ONIONS} and "
            f"{settings.BATCH_MAX_ASSESSED_ONIONS} "
            f"(got {assessed_onions}).",
        )
    if len(images) > settings.OPENROUTER_MAX_IMAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many images: {len(images)} "
            f"(limit {settings.OPENROUTER_MAX_IMAGES}).",
        )
    raw_images: List[bytes] = []
    for upload in images:
        if upload.content_type and not upload.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Expected image uploads, got '{upload.content_type}'.",
            )
        data = await upload.read()
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty image upload.",
            )
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Image upload exceeds the 12MB limit.",
            )
        raw_images.append(data)

    scan = None
    if scan_id is not None:
        result = await db.execute(select(Scan).where(Scan.id == scan_id))
        scan = result.scalar_one_or_none()
        if scan is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scan record not found.",
            )

    # 1-4. Roboflow detection per image (shared client); preserve evidence.
    # Per-image failures are kept as exception OBJECTS (not message strings)
    # so total failure maps to the right HTTP status via isinstance.
    evidence: List[RoboflowImageEvidence] = []
    roboflow_errors: List[RoboflowError] = []
    total_detections = 0
    conf_sum = 0.0
    conf_n = 0
    async with httpx.AsyncClient(
        timeout=settings.ROBOFLOW_TIMEOUT_SECONDS
    ) as rf_client:
        for index, raw in enumerate(raw_images):
            try:
                normalized = await RoboflowService.analyze_image(
                    raw, client=rf_client
                )
            except RoboflowError as exc:
                roboflow_errors.append(exc)
                evidence.append(
                    RoboflowImageEvidence(
                        image_index=index,
                        detection_count=0,
                        observed_classes=[],
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
                continue
            preds = normalized["predictions"]
            count = len(preds)
            mean_conf = (
                sum(p["confidence"] for p in preds) / count if count else None
            )
            total_detections += count
            if mean_conf is not None:
                conf_sum += sum(p["confidence"] for p in preds)
                conf_n += count
            evidence.append(
                RoboflowImageEvidence(
                    image_index=index,
                    detection_count=count,
                    mean_confidence=mean_conf,
                    observed_classes=normalized["observed_classes"],
                    image_width=normalized["image_width"],
                    image_height=normalized["image_height"],
                )
            )

    if roboflow_errors and len(roboflow_errors) == len(raw_images):
        # No detection evidence at all: fail loudly, never invent a grade.
        raise _map_provider_error(roboflow_errors[0])
    roboflow_failures = len(roboflow_errors)

    mean_conf_overall = (conf_sum / conf_n) if conf_n else None
    summary = _evidence_summary(
        evidence, total_detections, mean_conf_overall, assessed_onions
    )

    # 5-7. Provider batch assessment over the representative images.
    try:
        parsed = await OpenRouterService.assess_batch(raw_images, summary)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except OpenRouterError as exc:
        raise _map_provider_error(exc) from exc
    assessment = parsed["assessment"]
    warnings: List[str] = list(parsed["warnings"])

    # The grader-declared batch size is the denominator, preserved exactly.
    # A provider-estimated assessed count that differs is inconsistent
    # evidence: the declared value still wins and review is forced.
    provider_assessed = assessment.assessed_onions
    assessment = assessment.model_copy(
        update={"assessed_onions": assessed_onions}
    )
    if provider_assessed is not None and provider_assessed != assessed_onions:
        warnings.append(
            f"Provider-estimated assessed count ({provider_assessed}) differs "
            f"from the grader-declared batch size ({assessed_onions}); the "
            "declared value is used as the URS% denominator."
        )
    if (
        assessment.urs_onions is not None
        and assessment.urs_onions > assessed_onions
    ):
        # Impossible against the declared denominator: the URS evidence is
        # unusable (rejected, never clamped or invented around).
        warnings.append(
            f"Provider-estimated URS count ({assessment.urs_onions}) exceeds "
            f"the grader-declared batch size ({assessed_onions}); URS "
            "evidence rejected as inconsistent."
        )
        assessment = assessment.model_copy(
            update={"urs_onions": None, "assessed_onions": None}
        )

    # 8-9. Deterministic policy owns the final grade.
    has_high = any(
        issue.severity.value == "high"
        for issue in assessment.visible_quality_issues
    )
    try:
        decision = BatchGradingPolicy.grade_batch(
            assessment=assessment,
            total_detections=total_detections,
            has_high_severity_issue=has_high,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    review_required = decision.review_required
    review_reasons = list(decision.reasons) + warnings
    if provider_assessed is not None and provider_assessed != assessed_onions:
        # Declared-vs-estimated denominator conflict: a human must resolve it.
        review_required = True
        review_reasons.append(
            "Grader-declared batch size and provider estimate disagree; "
            "human review required."
        )
    if len(raw_images) < settings.BATCH_MIN_VIEWS:
        # Too few views for a representative multi-view assessment.
        review_required = True
        review_reasons.append(
            f"Only {len(raw_images)} view(s) submitted (minimum "
            f"{settings.BATCH_MIN_VIEWS}); complete all views for a "
            "representative batch assessment."
        )
    if roboflow_failures:
        review_required = True
        review_reasons.append(
            f"{roboflow_failures}/{len(raw_images)} image(s) failed Roboflow "
            "detection; assessment is based on partial evidence."
        )
    review_reasons.append(
        "View detections are NOT unique onions: the same physical onions may "
        f"appear in multiple views. URS% uses the grader-declared batch size "
        f"({assessed_onions}) as its denominator — never summed detections."
    )

    urs_percent = compute_urs_percent(
        assessment.urs_onions, assessment.assessed_onions
    )

    batch_id = str(uuid4())
    calculated_at = datetime.utcnow()
    row = BatchAssessment(
        id=batch_id,
        scan_id=scan.id if scan else None,
        status="human_review" if review_required else "completed",
        final_grade=decision.final_grade.value,
        assessment_confidence=assessment.assessment_confidence,
        sample_size=total_detections,
        sample_size_estimated=True,
        images_analyzed=len(raw_images),
        urs_percent=urs_percent,
        assessed_onions_declared=assessed_onions,
        review_required=review_required,
        review_reasons_json=json.dumps(review_reasons),
        policy_version=settings.BATCH_POLICY_VERSION,
        roboflow_model=settings.ROBOFLOW_MODEL_ID,
        assessment_model=settings.OPENROUTER_MODEL_ID,
        observations_json=json.dumps(assessment.observations),
        issues_json=json.dumps([i.model_dump() for i in assessment.visible_quality_issues]),
        evidence_json=json.dumps([e.model_dump() for e in evidence]),
        calculated_at=calculated_at,
    )
    db.add(row)

    await AuditService.record_event(
        db=db,
        action="BATCH_ASSESSED",
        entity_type="BatchAssessment",
        entity_id=batch_id,
        actor_id=current_user.id,
        payload={
            "batch_id": batch_id,
            "scan_id": scan.id if scan else None,
            "final_grade": decision.final_grade.value,
            "assessment_confidence": assessment.assessment_confidence,
            "sample_size": total_detections,
            "sample_size_estimated": True,
            "images_analyzed": len(raw_images),
            "urs_percent": urs_percent,
            "assessed_onions_declared": assessed_onions,
            "review_required": review_required,
            "policy_version": settings.BATCH_POLICY_VERSION,
            "roboflow_model": settings.ROBOFLOW_MODEL_ID,
            "assessment_model": settings.OPENROUTER_MODEL_ID,
        },
    )
    await db.commit()

    return BatchAssessResponse(
        final_grade=decision.final_grade,
        assessment_confidence=assessment.assessment_confidence,
        sample_size=total_detections,
        sample_size_estimated=True,
        images_analyzed=len(raw_images),
        urs_percent=urs_percent,
        assessed_onions_declared=assessed_onions,
        evidence=evidence,
        observations=assessment.observations,
        visible_quality_issues=assessment.visible_quality_issues,
        review_required=review_required,
        review_reasons=review_reasons,
        policy_version=settings.BATCH_POLICY_VERSION,
        roboflow_model=settings.ROBOFLOW_MODEL_ID,
        assessment_model=settings.OPENROUTER_MODEL_ID,
        batch_id=batch_id,
        calculated_at=calculated_at,
    )
