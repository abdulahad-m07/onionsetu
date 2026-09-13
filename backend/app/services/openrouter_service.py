# backend/app/services/openrouter_service.py
"""Dedicated server-side adapter for batch visual assessment via OpenRouter.

Single place in the codebase allowed to talk to OpenRouter. Same
isolation/quality bar as RoboflowService:
  1. validate server-side configuration (key never leaves the backend),
  2. normalize representative batch images (Pillow: RGB, EXIF-aware, capped
     size, JPEG),
  3. build a structured prompt embedding validated Roboflow evidence,
  4. POST to the OpenRouter OpenAI-compatible chat-completions API with a
     JSON response format,
  5. strictly validate the structured output (never trust it blindly).

Wire contract (OpenRouter OpenAI-compatible API):
  POST {OPENROUTER_API_URL}/chat/completions
  header `Authorization: Bearer KEY` (header ONLY — never in URL or body,
  so the key cannot leak via logs);
  images as multimodal `image_url` parts with base64 data URLs, one request
  for the whole representative batch (never one request per onion);
  structured output via `response_format: {"type": "json_object"}` (the
  prompt itself demands JSON, as json_object mode requires);
  answer text in `choices[0].message.content` with `finish_reason == "stop"`.

Never returns fabricated output: every failure raises a typed exception so
callers mark assessments failed/pending/review instead of inventing grades.
"""
import base64
import io
import json
from typing import Any, Dict, List, Optional, Tuple

import httpx
from PIL import Image, ImageOps

from backend.app.config.settings import settings
from backend.app.schemas.batch import (
    BatchGradeEnum,
    BatchVisualAssessment,
)

MAX_UPLOAD_BYTES = 12 * 1024 * 1024


class OpenRouterError(Exception):
    """Base class for all OpenRouter adapter failures."""


class OpenRouterConfigError(OpenRouterError):
    """Server is not configured (missing API key)."""


class OpenRouterAuthError(OpenRouterError):
    """OpenRouter rejected the credentials (401/403)."""


class OpenRouterAPIError(OpenRouterError):
    """OpenRouter returned an error status or the network failed.

    Carries the upstream HTTP status when known so routes can pass
    rate limiting (429) through instead of inviting retry storms.
    """

    def __init__(self, message: str, upstream_status: int | None = None):
        super().__init__(message)
        self.upstream_status = upstream_status


class OpenRouterTimeoutError(OpenRouterAPIError):
    """OpenRouter request timed out."""


class OpenRouterResponseError(OpenRouterError):
    """OpenRouter returned empty/malformed output or invalid schema."""


SYSTEM_INSTRUCTION = (
    "You are an agricultural quality assistant supporting onion procurement "
    "grading at APMC centers in India. Assess the photographed onion batch "
    "as a whole lot. Report ONLY what is visible in the images and the "
    "supplied detection evidence. Do NOT invent counts, measurements, "
    "variety names, moisture readings, or any data not provided. When "
    "uncertain, say so and set review_required to true. "
    "Return your answer as a single JSON object."
)


class OpenRouterService:
    @staticmethod
    def normalize_image(image_bytes: bytes) -> bytes:
        """Normalize one upload to RGB JPEG capped at OPENROUTER_MAX_IMAGE_DIM.

        Strips EXIF/metadata and bounds request size. Raises ValueError for
        undecodable input (caller decides skip-vs-reject; never faked).
        """
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                # Honor EXIF orientation so phone photos assess upright.
                oriented = ImageOps.exif_transpose(img)
                rgb = oriented.convert("RGB")
                rgb.thumbnail(
                    (settings.OPENROUTER_MAX_IMAGE_DIM, settings.OPENROUTER_MAX_IMAGE_DIM)
                )
                out = io.BytesIO()
                rgb.save(out, format="JPEG", quality=82)
                return out.getvalue()
        except Exception as exc:
            raise ValueError(f"Undecodable image upload: {exc}") from exc

    @staticmethod
    def build_prompt(evidence_summary: str, image_count: int) -> str:
        """Build the batch assessment prompt (pure helper, no I/O)."""
        return (
            "Assess this onion procurement batch from the "
            f"{image_count} representative image(s) attached.\n\n"
            "STRUCTURED DETECTION EVIDENCE (from the Roboflow onion "
            "detector — authoritative for counts/boxes, NOT for quality):\n"
            f"{evidence_summary}\n\n"
            "Return a single JSON object with: batch_assessment (overall verdict "
            "in 2-4 sentences), observations (a JSON array of strings, one "
            "per visible fact — never a single concatenated string), "
            "visible_quality_issues (a JSON array of objects shaped exactly "
            "like {\"issue\": \"...\", \"severity\": \"low|medium|high\", "
            "\"evidence_ref\": \"image N\"}), uncertainty_notes, "
            "assessment_confidence (0.0-1.0, your certainty in THIS "
            "assessment — NOT a grade percentage), suggested_grade (exactly "
            "one of A, B, C, Reject, or omit if you cannot judge), "
            "review_required (true when uncertain or evidence is weak), "
            "images_analyzed, urs_onions (your estimated count of onions "
            "showing under-grade signs, or omit if you cannot estimate), "
            "assessed_onions (your estimated count of onions you could "
            "actually assess, or omit if you cannot estimate). "
            "Estimates must be honest: if you cannot estimate a count, omit "
            "it rather than guessing."
        )

    @staticmethod
    def build_request(
        images: List[Tuple[str, str]], evidence_summary: str
    ) -> Dict[str, Any]:
        """Build the chat-completions request (pure helper, no I/O).

        `images` = [(mime_type, base64_data), ...]. The API key is placed in
        the `Authorization: Bearer` HEADER only — never in the URL or body —
        so it cannot leak via logs. Raises OpenRouterConfigError when
        unconfigured.
        """
        api_key = settings.OPENROUTER_API_KEY
        if not api_key:
            raise OpenRouterConfigError(
                "OPENROUTER_API_KEY is not configured on the server. "
                "Set it via environment; never ship it to clients."
            )
        if not images:
            raise ValueError("At least one normalized image is required.")
        url = f"{settings.OPENROUTER_API_URL.rstrip('/')}/chat/completions"
        content: List[Dict[str, Any]] = [
            {"type": "text", "text": OpenRouterService.build_prompt(evidence_summary, len(images))}
        ]
        for mime_type, b64 in images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                }
            )
        body = {
            "model": settings.OPENROUTER_MODEL_ID,
            "temperature": 0.2,
            "max_tokens": 2000,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": content},
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        return {"url": url, "headers": headers, "body": body}

    @staticmethod
    def _message_text(message: Dict[str, Any]) -> str:
        """Extract assistant text, tolerating string or content-part lists."""
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("text")
            )
        return ""

    @staticmethod
    def parse_response(payload: Dict[str, Any], images_sent: int) -> Dict[str, Any]:
        """Strictly validate a chat-completions payload.

        Returns {"assessment": BatchVisualAssessment, "warnings": [...]}.
        An invalid `suggested_grade` discards ONLY the suggestion (forcing
        review) — the rest of a valid assessment is preserved. Anything
        structurally wrong raises OpenRouterResponseError.
        """
        if not isinstance(payload, dict):
            raise OpenRouterResponseError("OpenRouter response is not a JSON object.")
        error = payload.get("error")
        if error:
            raise OpenRouterResponseError(
                f"OpenRouter returned an error payload: {json.dumps(error)[:300]}"
            )
        choices = payload.get("choices")
        if not choices:
            raise OpenRouterResponseError("OpenRouter returned no choices.")
        first = choices[0]
        finish = first.get("finish_reason")
        if finish != "stop":
            raise OpenRouterResponseError(
                f"OpenRouter did not complete normally: finish_reason={finish!r}."
            )
        message = first.get("message") or {}
        raw = OpenRouterService._message_text(message).strip()
        if not raw:
            raise OpenRouterResponseError("OpenRouter returned empty message content.")
        try:
            data = json.loads(raw)
        except ValueError as exc:
            raise OpenRouterResponseError(
                "OpenRouter did not return valid JSON."
            ) from exc
        if not isinstance(data, dict):
            raise OpenRouterResponseError("OpenRouter JSON is not an object.")

        warnings: List[str] = []
        suggested = data.get("suggested_grade")
        if suggested is not None:
            valid = {g.value for g in BatchGradeEnum}
            if suggested not in valid:
                warnings.append(
                    f"Discarded invalid suggested_grade {suggested!r}; "
                    "forcing human review."
                )
                data["suggested_grade"] = None
                data["review_required"] = True
        try:
            assessment = BatchVisualAssessment(**data)
        except Exception as exc:
            raise OpenRouterResponseError(
                f"OpenRouter output failed schema validation: {exc}"
            ) from exc
        # Pipeline fact, not an AI claim: how many images were actually sent.
        assessment.images_analyzed = images_sent
        return {"assessment": assessment, "warnings": warnings}

    @staticmethod
    async def assess_batch(
        raw_images: List[bytes],
        evidence_summary: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """Run batch assessment over raw uploads; return validated output."""
        if not raw_images:
            raise ValueError("At least one image is required.")
        if len(raw_images) > settings.OPENROUTER_MAX_IMAGES:
            raise ValueError(
                f"Too many images: {len(raw_images)} "
                f"(limit {settings.OPENROUTER_MAX_IMAGES})."
            )
        normalized: List[Tuple[str, str]] = []
        skipped = 0
        for raw in raw_images:
            if not raw or len(raw) > MAX_UPLOAD_BYTES:
                skipped += 1
                continue
            try:
                jpeg = OpenRouterService.normalize_image(raw)
            except ValueError:
                skipped += 1
                continue
            normalized.append(
                ("image/jpeg", base64.b64encode(jpeg).decode("ascii"))
            )
        if not normalized:
            raise OpenRouterResponseError("No usable images after normalization.")
        request = OpenRouterService.build_request(normalized, evidence_summary)

        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(timeout=settings.OPENROUTER_TIMEOUT_SECONDS)
        try:
            try:
                response = await client.post(
                    request["url"],
                    headers=request["headers"],
                    json=request["body"],
                )
            except httpx.TimeoutException as exc:
                raise OpenRouterTimeoutError(
                    "Batch assessment timed out after "
                    f"{settings.OPENROUTER_TIMEOUT_SECONDS}s."
                ) from exc
            except httpx.HTTPError as exc:
                raise OpenRouterAPIError(
                    f"Batch assessment request failed (network): {exc}"
                ) from exc

            if response.status_code in (401, 403):
                raise OpenRouterAuthError(
                    "OpenRouter rejected the server API key (401/403). "
                    "Check OPENROUTER_API_KEY."
                )
            if response.status_code != 200:
                raise OpenRouterAPIError(
                    f"OpenRouter returned HTTP {response.status_code}: "
                    f"{response.text[:300]}",
                    upstream_status=response.status_code,
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise OpenRouterResponseError(
                    "OpenRouter returned non-JSON data."
                ) from exc
            parsed = OpenRouterService.parse_response(payload, len(normalized))
            if skipped:
                parsed["warnings"].append(
                    f"{skipped} upload(s) were unusable and excluded; "
                    f"{len(normalized)} image(s) analyzed."
                )
            return parsed
        finally:
            if owns_client:
                await client.aclose()
