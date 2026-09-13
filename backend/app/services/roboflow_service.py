# backend/app/services/roboflow_service.py
"""Dedicated server-side adapter for Roboflow hosted vision inference.

Single place in the codebase allowed to talk to Roboflow. Responsibilities:
  1. receive raw image bytes,
  2. POST them to the configured Roboflow Serverless model
     (auth via server-side ROBOFLOW_API_KEY only),
  3. validate the real response,
  4. normalize it into OnionSetu's internal prediction schema.

Never returns fabricated output: every failure mode raises a typed
exception so callers can mark scans FAILED / retry instead of inventing
detections, classes, or confidence values.

Roboflow Serverless contract (docs.roboflow.com, verified against the live
endpoint with an invalid-key probe):
  POST {ROBOFLOW_API_URL}/{ROBOFLOW_MODEL_ID}?api_key=...&confidence=..&overlap=..
  body: raw base64 image, Content-Type: application/x-www-form-urlencoded
  -> {"predictions": [{"x": cx_px, "y": cy_px, "width": px, "height": px,
                       "class": str, "class_id": int, "confidence": 0..1,
                       "detection_id": str}], "image": {"width": w, "height": h}}
  x/y are CENTER coordinates in submitted-image pixels.
"""
import base64
from typing import Any, Dict, List, Optional

import httpx

from backend.app.config.settings import settings
from backend.app.models.scan import DefectTypeEnum


class RoboflowError(Exception):
    """Base class for all Roboflow adapter failures."""


class RoboflowConfigError(RoboflowError):
    """Server is not configured (missing API key)."""


class RoboflowAuthError(RoboflowError):
    """Roboflow rejected the credentials (401/403)."""


class RoboflowAPIError(RoboflowError):
    """Roboflow returned an error status or the network failed.

    Carries the upstream HTTP status when known so routes can pass
    quota exhaustion (429) through instead of inviting retry storms.
    """

    def __init__(self, message: str, upstream_status: int | None = None):
        super().__init__(message)
        self.upstream_status = upstream_status


class RoboflowTimeoutError(RoboflowAPIError):
    """Roboflow request timed out."""


class RoboflowResponseError(RoboflowError):
    """Roboflow returned malformed/unexpected data."""


# Raw Roboflow class label (lowercased, trimmed) -> OnionSetu defect type.
# Only labels in this map count as quality classification. Anything else
# (e.g. a generic "onion" detector label) passes through as UNKNOWN and
# forces quality_classification_available=False downstream.
QUALITY_CLASS_MAP = {
    "gradea": DefectTypeEnum.GRADE_A,
    "grade a": DefectTypeEnum.GRADE_A,
    "grade_a": DefectTypeEnum.GRADE_A,
    "healthy": DefectTypeEnum.GRADE_A,
    "damaged": DefectTypeEnum.DAMAGED,
    "damage": DefectTypeEnum.DAMAGED,
    "bruised": DefectTypeEnum.DAMAGED,
    "rotten": DefectTypeEnum.ROTTEN,
    "rot": DefectTypeEnum.ROTTEN,
    "decay": DefectTypeEnum.ROTTEN,
    "mold": DefectTypeEnum.ROTTEN,
    "sprouted": DefectTypeEnum.SPROUTED,
    "sprout": DefectTypeEnum.SPROUTED,
    "undersized": DefectTypeEnum.UNDERSIZED,
    "undersize": DefectTypeEnum.UNDERSIZED,
    "small": DefectTypeEnum.UNDERSIZED,
}

MAX_IMAGE_BYTES = 12 * 1024 * 1024


class RoboflowService:
    @staticmethod
    def build_request(image_bytes: bytes) -> Dict[str, Any]:
        """Build the Serverless request (URL, params, body, headers).

        Pure helper — separated so tests can assert request construction
        without performing any network I/O.
        """
        if not image_bytes:
            raise RoboflowResponseError("Empty image payload.")
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise RoboflowResponseError(
                f"Image payload too large: {len(image_bytes)} bytes "
                f"(limit {MAX_IMAGE_BYTES})."
            )
        api_key = settings.ROBOFLOW_API_KEY
        if not api_key:
            raise RoboflowConfigError(
                "ROBOFLOW_API_KEY is not configured on the server. "
                "Set it via environment; never ship it to clients."
            )
        url = f"{settings.ROBOFLOW_API_URL.rstrip('/')}/{settings.ROBOFLOW_MODEL_ID}"
        params = {
            "api_key": api_key,
            "confidence": settings.ROBOFLOW_MIN_CONFIDENCE,
            "overlap": settings.ROBOFLOW_OVERLAP,
        }
        body = base64.b64encode(image_bytes).decode("ascii")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        return {"url": url, "params": params, "body": body, "headers": headers}

    @staticmethod
    def normalize_response(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a Roboflow JSON payload and normalize predictions.

        Raises RoboflowResponseError on malformed top-level data.
        Individual malformed predictions are skipped and counted in
        `dropped_invalid_predictions` (never silently fixed up).
        """
        if not isinstance(payload, dict):
            raise RoboflowResponseError("Roboflow response is not a JSON object.")
        raw_predictions = payload.get("predictions")
        if not isinstance(raw_predictions, list):
            raise RoboflowResponseError(
                "Roboflow response is missing the 'predictions' array."
            )
        image_info = payload.get("image") or {}
        image_width = image_info.get("width", 0)
        image_height = image_info.get("height", 0)

        normalized: List[Dict[str, Any]] = []
        observed: List[str] = []
        dropped = 0
        for item in raw_predictions:
            try:
                pred = RoboflowService._normalize_prediction(item)
            except (KeyError, TypeError, ValueError):
                dropped += 1
                continue
            normalized.append(pred)
            if pred["roboflow_class"] not in observed:
                observed.append(pred["roboflow_class"])

        quality_available = len(normalized) > 0 and all(
            p["quality_mapped"] for p in normalized
        )
        return {
            "model_id": settings.ROBOFLOW_MODEL_ID,
            "image_width": int(image_width or 0),
            "image_height": int(image_height or 0),
            "predictions": normalized,
            "observed_classes": sorted(observed),
            "quality_classification_available": quality_available,
            "dropped_invalid_predictions": dropped,
        }

    @staticmethod
    def _normalize_prediction(item: Dict[str, Any]) -> Dict[str, Any]:
        cx = float(item["x"])
        cy = float(item["y"])
        w = float(item["width"])
        h = float(item["height"])
        raw_class = str(item["class"])
        confidence = float(item["confidence"])
        if w <= 0 or h <= 0:
            raise ValueError("Non-positive box dimensions.")
        if not (0.0 <= confidence <= 1.0):
            raise ValueError("Confidence outside [0, 1].")

        defect_type = QUALITY_CLASS_MAP.get(raw_class.strip().lower())
        return {
            # Center -> top-left corner conversion (Roboflow uses centers).
            "x": cx - w / 2.0,
            "y": cy - h / 2.0,
            "width": w,
            "height": h,
            "roboflow_class": raw_class,
            "class_id": item.get("class_id"),
            "confidence": confidence,
            "detection_id": item.get("detection_id"),
            "defect_type": (
                defect_type.value if defect_type else DefectTypeEnum.UNKNOWN.value
            ),
            "quality_mapped": defect_type is not None,
        }

    @staticmethod
    async def analyze_image(
        image_bytes: bytes,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """Send image bytes to Roboflow and return the normalized result."""
        request = RoboflowService.build_request(image_bytes)

        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(
                timeout=settings.ROBOFLOW_TIMEOUT_SECONDS
            )
        try:
            try:
                response = await client.post(
                    request["url"],
                    params=request["params"],
                    content=request["body"],
                    headers=request["headers"],
                )
            except httpx.TimeoutException as exc:
                raise RoboflowTimeoutError(
                    f"Roboflow inference timed out after "
                    f"{settings.ROBOFLOW_TIMEOUT_SECONDS}s."
                ) from exc
            except httpx.HTTPError as exc:
                raise RoboflowAPIError(
                    f"Roboflow request failed (network): {exc}"
                ) from exc

            if response.status_code in (401, 403):
                raise RoboflowAuthError(
                    "Roboflow rejected the server API key (401/403). "
                    "Check ROBOFLOW_API_KEY."
                )
            if response.status_code != 200:
                raise RoboflowAPIError(
                    f"Roboflow returned HTTP {response.status_code}: "
                    f"{response.text[:300]}",
                    upstream_status=response.status_code,
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise RoboflowResponseError(
                    "Roboflow returned non-JSON data."
                ) from exc
            return RoboflowService.normalize_response(payload)
        finally:
            if owns_client:
                await client.aclose()
