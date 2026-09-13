# OnionSetu — Roboflow Vision Integration Specification (CONTRACT, v4.0.0)

> v4.0.0 replaces the batch visual assessment provider: Roboflow (detection)
> + Qwen2.5-VL 72B via OpenRouter (batch visual assessment) + deterministic
> OnionSetu policy → ONE final grade A/B/C/Reject. Gemini 3.1 Pro was
> removed as an active runtime provider. v2.0.0 per-image inference contracts
> below still apply to the detection stage. Supersedes v1.0.0 (YOLOv8 +
> MobileNetV2 + TFLite), which is RETIRED.

> Supersedes v1.0.0 (YOLOv8 + MobileNetV2 + TFLite), which is RETIRED.
> Active AI layer: ONE hosted Roboflow vision model called server-side.
>
> Model truth (verified 2026-09-13): `onion-yhzc7-mo9ib/1` is live on
> `https://serverless.roboflow.com` (invalid-key probe returned Roboflow's
> `401 {"status":401,...}`, proving the deployment exists), but its class
> list is UNDISCOVERED — no API key was available at migration time and the
> model is not in the public Universe index. This spec therefore requires
> verbatim label passthrough with explicit quality-availability flagging,
> and forbids inventing quality classes the model has not demonstrated.

Reference code: `backend/app/services/roboflow_service.py`,
`backend/app/routes/inference.py`, `backend/app/schemas/inference.py`,
`frontend/lib/ml/model_contract.dart`,
`frontend/lib/models/roboflow_inference.dart`,
`frontend/lib/services/api_service.dart` (`analyzeImage`),
`frontend/lib/providers/scan_provider.dart` (`requestAiAnalysis`),
`frontend/lib/services/grading_engine.dart`.

---

## 1. Serving model

| Item | Value |
|---|---|
| Model id | `onion-yhzc7-mo9ib/1` (backend `ROBOFLOW_MODEL_ID`) |
| Runtime | Roboflow Serverless (`ROBOFLOW_API_URL`, default `https://serverless.roboflow.com`) |
| Auth | `ROBOFLOW_API_KEY` environment variable, server-side ONLY. Never in Flutter code/assets/bundles, JS, git, or committed env files |
| Target | ONE vision model detecting `gradeA`, `damaged`, `rotten`, `sprouted`, `undersized`, each with real box + class + confidence. Until the deployment provides all five, quality classification is UNAVAILABLE (see §4) |

## 2. Request contract (backend owns)

`POST {ROBOFLOW_API_URL}/{ROBOFLOW_MODEL_ID}?api_key=...&confidence={ROBOFLOW_MIN_CONFIDENCE}&overlap={ROBOFLOW_OVERLAP}`,
body = raw base64 image, `Content-Type: application/x-www-form-urlencoded`.
Defaults: timeout 30s, confidence 45 (0–100), overlap 30 (NMS IoU 0–100).
Implemented once in `RoboflowService.build_request()` — do not scatter
Roboflow calls elsewhere.

## 3. Response contract (validated, never trusted blindly)

Raw Roboflow object-detection shape:
`{"predictions": [{"x": center_px, "y": center_px, "width": px, "height": px,
"class": str, "class_id": int, "confidence": 0..1, "detection_id": str}],
"image": {"width": w, "height": h}}`.

Normalized OnionSetu schema (`schemas/inference.py`, mirrored in
`models/roboflow_inference.dart`): top-left `x/y` in submitted-image pixels
(center − size/2), `width/height > 0`, `confidence ∈ [0,1]`, verbatim
`roboflow_class`, mapped `defect_type` (or `unknown`), `quality_mapped` bool,
plus envelope `model_id`, `image_width/height`, `observed_classes`,
`quality_classification_available`, `dropped_invalid_predictions`.
Malformed top level → `RoboflowResponseError`; malformed items are skipped
AND counted, never repaired. Timeouts/auth/5xx/network map to typed errors.

## 4. Class mapping (no fabrication)

`QUALITY_CLASS_MAP` (backend) / `qualityClassMap` (Flutter, kept in sync):
`gradea|grade a|grade_a|healthy → gradeA`, `damaged|damage|bruised → damaged`,
`rotten|rot|decay|mold → rotten`, `sprouted|sprout → sprouted`,
`undersized|undersize|small → undersized`. Everything else (e.g. `onion`) →
`unknown` + `quality_mapped=false`.
`quality_classification_available` = at least one prediction AND all mapped.
Grading (`grading_engine.dart`): unknown items count in total, never in the
Grade A numerator, and ALWAYS force `borderlineReview` (human review). The
model NEVER outputs Grade A / URS percentages; the engine calculates them.

## 5. Confidence handling

`DetectionItem.confidence` = the model's own `confidence`, end to end.
No brightness/random/constant formulas exist anywhere in the pipeline
(verified removed). Detection pre-filter 0.45 server-side; grading gate mean
≥ 0.70 → `highConfidence` else `borderlineReview`, with forced review when
quality classes are unavailable.

## 6. Size estimation (no neural network)

`OnionSizeEstimator` (unchanged math): `sqrt(w·h)/3.8 px/mm`, clamped
15–140mm, from REAL box geometry. Calibration (`3.8 px/mm` @ 40cm) is an
assumption, documented in `LIMITATIONS.md` — mm values are estimates until a
tray-marker/fixed-rig calibration lands.

## 7. Offline behaviour

Capture + quality gate + SQLite work fully offline with
`AiInferenceStatus.pendingAi`. `requestAiAnalysis()` requires connectivity,
retries transport/5xx (client, 3 attempts), and returns true ONLY on
validated predictions. States: `pendingAi → processing →
completed | humanReviewRequired | failed`. `failed` keeps local data for
retry. Reports/sync only consume completed/reviewed results.

## 8. What the five-class upgrade requires (when retraining)

Retrain/replace the Roboflow deployment so it natively returns the five
quality labels; no app code changes needed — the maps, grading, review gate,
and report banner already key off `quality_classification_available`. Then:
verify observed classes on real procurement photos, measure per-class
precision/confidence calibration, and re-tune `ROBOFLOW_MIN_CONFIDENCE` and
the 0.70 grading gate from measured data (never from guesses).

## 9. Retired (do not revive)

`yolov8n.tflite` / `mobilenetv2.tflite` requirements, `tflite_flutter`
dependency (removed from `pubspec.yaml`/lock), grid detections, pixel-color
defect heuristics, brightness confidence, and any on-device `Interpreter`
production path (`ml_inference_service.dart` is a retired shim retaining only
tested geometry helpers).

---

## 10. Batch grading layer (v4.0.0): Roboflow + Qwen2.5-VL 72B → A/B/C/Reject

Reference code: `backend/app/services/openrouter_service.py`,
`backend/app/services/batch_policy.py`, `backend/app/routes/batch.py`
(`POST /v1/inference/batch-assess`), `backend/app/schemas/batch.py`,
`backend/app/models/batch.py` (`batch_assessments` table),
`frontend/lib/models/batch_assessment.dart`,
`frontend/lib/providers/scan_provider.dart` (`requestBatchAssessment`),
`frontend/lib/db/scan_database.dart` (v4).

### 10.1 Responsibilities (strict separation)

- **Roboflow** (`onion-yhzc7-mo9ib/1`, tested: `class="onion"` ≈ 0.9765):
  detection only — boxes + real confidence + verbatim labels. Never assigns
  A/B/C/Reject; `"onion"` is never Grade A.
- **Qwen2.5-VL 72B via OpenRouter** (`qwen/qwen2.5-vl-72b-instruct:free`,
  OpenAI-compatible chat-completions API): batch visual reasoning over the
  representative images + structured Roboflow evidence. Returns observations,
  visible issues with severity, estimated URS counts (`urs_onions` /
  `assessed_onions`, omitted when unknowable), uncertainty notes,
  `assessment_confidence` (certainty, NOT a grade share), review flag, and at
  most a grade SUGGESTION. The provider's estimated `assessed_onions` never
  becomes the denominator: the route pins the grader-declared batch size
  (100-200) and forces review on any conflict. Never trusted blindly: invalid suggestions are
  discarded (review forced), inconsistent URS counts are rejected, and the
  provider may not invent measurements (enforced by prompt + strict schema
  validation).
- **OnionSetu batch policy** (`BATCH_POLICY_VERSION=v0.2-provisional`,
  NOT official AGMARK/APMC boundaries): deterministic, owns the final grade.
  PRIMARY driver is URS% = (URS onions / assessed onions) x 100 from the
  provider's estimated URS evidence: A<=5%, B<=10%, C<=20%, else Reject.
  The AI suggestion is supporting evidence only (mismatch forces review);
  unknown URS evidence forces review with the configured fallback. Applies
  the confidence gate and high-severity cap. All thresholds are explicitly
  PROVISIONAL — no official APMC A/B/C/Reject thresholds exist in this repo
  (BLOCKER).

### 10.2 OpenRouter wire contract (Qwen2.5-VL 72B)

`POST {OPENROUTER_API_URL}/chat/completions` with `Authorization: Bearer`
header only (key never in URL/body/logs); images as multimodal `image_url`
data-URL parts in ONE request for the whole representative batch (never one
request per onion); structured output via `response_format:
{"type": "json_object"}` with the prompt itself demanding JSON; answer in
`choices[0].message.content` with `finish_reason == "stop"`. Non-stop,
empty, non-JSON, error-payload, or schema-violating output → typed error,
never a grade. Timeouts/auth/5xx/network → typed errors mapped to
503/502/504; upstream rate limiting (429) passes through as HTTP 429 so
clients fail fast instead of retrying into a depleted quota. Server-side
Pillow normalization (RGB JPEG, EXIF-transposed, ≤1024px, ≤15 images) is
reused unchanged from the previous provider adapter.

### 10.3 Batch flow & truthfulness invariants

Images → Roboflow each (partial failure proceeds with flagged partial
evidence; total failure aborts, no grade) → evidence summary (view
detections explicitly NOT unique onions; grader-declared batch size carried
as the denominator context) → OpenRouter/Qwen assessment → declared-count
pinning (provider estimate conflicts force review; impossible URS counts
rejected) → policy → persist +
`BATCH_ASSESSED` audit → response with exactly one `final_grade ∈
{A,B,C,Reject}` plus the grounding `urs_percent` and the echoed
`assessed_onions_declared`. Offline: captures stay `pendingAi`; failures preserve scans
+ evidence for retry. Three confidences stay separate: Roboflow detection
mean, provider assessment confidence, final grade decision. Report shows the
batch card only when a validated assessment exists; sync carries optional
batch payloads idempotently.
