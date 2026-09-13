# backend/app/routes/inference.py
from uuid import uuid4
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config.database import get_db
from backend.app.models.user import User
from backend.app.schemas.inference import InferenceAnalyzeResponse
from backend.app.services.auth_service import get_current_user
from backend.app.services.audit_service import AuditService
from backend.app.services.roboflow_service import (
    RoboflowAPIError,
    RoboflowAuthError,
    RoboflowConfigError,
    RoboflowError,
    RoboflowResponseError,
    RoboflowService,
    RoboflowTimeoutError,
)

router = APIRouter(prefix="/inference", tags=["AI Inference"])

MAX_UPLOAD_BYTES = 12 * 1024 * 1024


@router.post("/analyze", response_model=InferenceAnalyzeResponse)
async def analyze_image(
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if image.content_type and not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expected an image upload, got '{image.content_type}'.",
        )
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty image upload.",
        )
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image upload exceeds the 12MB limit.",
        )

    try:
        result = await RoboflowService.analyze_image(image_bytes)
    except RoboflowConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except RoboflowAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except RoboflowTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(exc),
        ) from exc
    except (RoboflowAPIError, RoboflowResponseError) as exc:
        if getattr(exc, "upstream_status", None) == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(exc),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except RoboflowError as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    # Cover the AI call in the append-only audit chain (never blocks response).
    inference_id = str(uuid4())
    await AuditService.record_event(
        db=db,
        action="ROBOFLOW_INFERENCE",
        entity_type="Inference",
        entity_id=inference_id,
        actor_id=current_user.id,
        payload={
            "inference_id": inference_id,
            "model_id": result["model_id"],
            "prediction_count": len(result["predictions"]),
            "observed_classes": result["observed_classes"],
            "quality_classification_available": result[
                "quality_classification_available"
            ],
        },
    )
    await db.commit()

    return InferenceAnalyzeResponse(**result)
