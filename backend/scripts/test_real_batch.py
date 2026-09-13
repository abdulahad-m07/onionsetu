# backend/scripts/test_real_batch.py
"""Developer integration script: REAL Roboflow + REAL OpenRouter batch run.

Uses real onion images from the local dataset and the EXISTING
production adapters (no behavior changes, no mocks):

  dataset images
  -> RoboflowService.analyze_image (real Serverless call per image)
  -> routes.batch._evidence_summary (EXACT prompt evidence builder)
  -> OpenRouterService.assess_batch (real OpenRouter chat-completions call)
  -> grader-declared denominator override (EXACT route logic)
  -> BatchGradingPolicy.grade_batch (deterministic ONE grade)

Prints evidence + validated assessment + final grade. Provider failures
(429 rate limit, auth, timeout) are printed as typed errors with a non-zero
exit — never faked into a successful grade.

Usage (keys from local gitignored .env, never printed):
  python backend/scripts/test_real_batch.py [N_IMAGES=10] [ASSESSED_ONIONS=150]
"""
import asyncio
import glob
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.config.settings import settings
from backend.app.routes.batch import _evidence_summary
from backend.app.schemas.batch import RoboflowImageEvidence
from backend.app.services.batch_policy import BatchGradingPolicy, compute_urs_percent
from backend.app.services.openrouter_service import OpenRouterError, OpenRouterService
from backend.app.services.roboflow_service import RoboflowError, RoboflowService

DATASET_DIR = r"C:\Users\abdul\Downloads\archive (2)\Onion Grading Dataset\test\images"


async def main(n_images: int, assessed_onions: int) -> int:
    print(f"Roboflow model : {settings.ROBOFLOW_MODEL_ID}")
    print(f"Assess model   : {settings.OPENROUTER_MODEL_ID}")
    print(f"Declared batch : {assessed_onions} onions (grader-declared denominator)")
    print(f"Roboflow key   : {'configured' if settings.ROBOFLOW_API_KEY else 'MISSING'}")
    print(f"OpenRouter key : {'configured' if settings.OPENROUTER_API_KEY else 'MISSING'}")
    if not settings.ROBOFLOW_API_KEY or not settings.OPENROUTER_API_KEY:
        print("BLOCKED: provider key(s) missing. Set them in local .env.")
        return 2

    files = sorted(glob.glob(os.path.join(DATASET_DIR, "*.jpg")))
    if len(files) < n_images:
        print(f"BLOCKED: only {len(files)} dataset images found.")
        return 2
    # Spread picks across the set for representative multi-view evidence.
    step = max(1, len(files) // n_images)
    chosen = [files[(i * step) % len(files)] for i in range(n_images)]
    print(f"Images ({len(chosen)}):")
    for path in chosen:
        print(f"  - {os.path.basename(path)}")

    raw_images = []
    for path in chosen:
        with open(path, "rb") as fh:
            raw_images.append(fh.read())

    # 1. REAL Roboflow detection per image.
    evidence = []
    total = 0
    conf_sum = 0.0
    conf_n = 0
    try:
        for index, raw in enumerate(raw_images):
            normalized = await RoboflowService.analyze_image(raw)
            preds = normalized["predictions"]
            count = len(preds)
            mean_conf = sum(p["confidence"] for p in preds) / count if count else None
            total += count
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
    except RoboflowError as exc:
        print(f"REAL ROBOFLOW FAILED: {type(exc).__name__}: {exc}")
        return 3

    mean_overall = (conf_sum / conf_n) if conf_n else None
    print(f"\nRoboflow observed classes: {sorted({c for e in evidence for c in e.observed_classes})}")
    print(f"Detection counts per image: {[e.detection_count for e in evidence]}")
    print(f"View detections (NOT unique onions): {total}")
    if mean_overall is not None:
        print(f"Mean detection confidence: {mean_overall:.4f}")
    print(f"Quality-mapped predictions: 0 expected "
          f"({'onion' if any('onion' in e.observed_classes for e in evidence) else 'no'} classes are detection-only)")

    summary = _evidence_summary(evidence, total, mean_overall, assessed_onions)

    # 2. REAL OpenRouter batch assessment (correct signature: images + summary).
    try:
        parsed = await OpenRouterService.assess_batch(raw_images, summary)
    except OpenRouterError as exc:
        print(f"\nREAL OPENROUTER FAILED: {type(exc).__name__}: {exc}")
        print("Batch data preserved above; retry when quota/connectivity allows.")
        return 4

    a = parsed["assessment"]
    print("\n--- Validated batch assessment ---")
    print(f"assessment_confidence : {a.assessment_confidence}")
    print(f"suggested_grade       : {a.suggested_grade}")
    print(f"review_required (AI)  : {a.review_required}")
    provider_assessed = a.assessed_onions
    # EXACT route logic: the grader-declared batch size is the denominator.
    a = a.model_copy(update={"assessed_onions": assessed_onions})
    if provider_assessed is not None and provider_assessed != assessed_onions:
        print(f"DENOMINATOR CONFLICT: provider estimated {provider_assessed}, "
              f"grader declared {assessed_onions} -> declared wins + review.")
    if a.urs_onions is not None and a.urs_onions > assessed_onions:
        print(f"URS EVIDENCE REJECTED: provider URS {a.urs_onions} exceeds "
              f"declared {assessed_onions}.")
        a = a.model_copy(update={"urs_onions": None, "assessed_onions": None})
    print(f"urs_onions (provider): {a.urs_onions}")
    print(f"assessed denominator : {a.assessed_onions}")
    print(f"URS%                 : {compute_urs_percent(a.urs_onions, a.assessed_onions)}")
    print(f"observations          : {a.observations}")
    print(f"issues                : {[ (i.issue, i.severity.value) for i in a.visible_quality_issues ]}")
    print(f"adapter warnings      : {parsed['warnings']}")

    # 3. Deterministic policy owns the final grade (suggestion never bypasses).
    decision = BatchGradingPolicy.grade_batch(
        assessment=a,
        total_detections=total,
        has_high_severity_issue=any(
            i.severity.value == "high" for i in a.visible_quality_issues
        ),
    )
    print("\n--- Deterministic policy decision ---")
    print(f"ONE FINAL GRADE: {decision.final_grade.value}")
    print(f"review_required : {decision.review_required}")
    print(f"reasons         : {decision.reasons}")
    return 0


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    declared = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    raise SystemExit(asyncio.run(main(n, declared)))
