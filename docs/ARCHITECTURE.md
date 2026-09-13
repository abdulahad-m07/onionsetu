# OnionSetu: System Architecture Specification

## 1. Overview
OnionSetu is an AI-powered offline-first mobile application and backend ecosystem designed to provide objective, transparent, and evidence-backed quality grading of onion batches at procurement centers. The product output is ONE final batch grade (**A / B / C / Reject**) per sampled lot, produced by a deterministic policy over Roboflow detection evidence and Qwen2.5-VL 72B batch visual assessment via OpenRouter.

---

## 2. Core Architecture Components

```
┌─────────────────────────────────────────────────────────────┐
│                 ONIONSETU CLIENT ARCHITECTURE               │
├───────────────────────────────┬─────────────────────────────┤
│  Flutter Mobile App UI        │  Cloud AI via Backend         │
│  - Guided 10–15 View Capture  │  - Roboflow Vision Model      │
│  - Quality Gate (Sharp/Lum)   │    (detection, server-side)   │
│  - Interactive Bounding Boxes │  - Qwen2.5-VL 72B (batch      │
│  - Confidence Gate Flagging   │    visual assessment)         │
│  - Pending-AI Offline Queue   │  - Validated Predictions      │
│  - Final A/B/C/Reject Card    │  - Deterministic Batch Policy │
├───────────────────────────────┴─────────────────────────────┤
│  Local SQLite Persistence (Scans, Images, Detections, Queue) │
└──────────────────────────────┬──────────────────────────────┘
                                │ (Pending-AI -> Online Inference -> Sync)
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                 BACKEND & CLOUD ARCHITECTURE                │
├─────────────────────────────────────────────────────────────┤
│  FastAPI REST API                                           │
│  - OTP & JWT Authentication (RBAC: Farmer / Grader / Admin) │
│  - POST /v1/inference/analyze (Roboflow adapter; API key    │
│    stays server-side; image in, validated predictions out)  │
│  - POST /v1/inference/batch-assess (Roboflow + Qwen2.5-VL   │
│    via OpenRouter + policy → ONE final A/B/C/Reject)        │
│  - Scan Ingestion & Paginated Search                        │
│  - Dispute Resolution State Machine                         │
│  - ReportLab PDF Certificate Generator                      │
├──────────────────────────────┬──────────────────────────────┤
│  PostgreSQL Database         │  Supabase Cloud Storage      │
│  - Users, Scans, Results     │  - Evidence Images & PDFs    │
│  - Immutable SHA-256 Chain   │                              │
│    (incl. ROBOFLOW_INFERENCE events)                        │
└──────────────────────────────┴──────────────────────────────┘
```

---

## 3. Data Flow Lifecycle
1. **Sampling**: Grader initiates lot session (`lot_number`, farmer details, APMC center) and enters the grader-counted physical batch size (100–200 onions) — the only URS% denominator.
2. **Guided Multi-Photo Capture**: 10–15 views of the SAME physical batch from cycling perspectives (Top 90°, Side 45°, Spread Reverse). Views are not new onions: per-view detection tallies are never summed as unique onions.
3. **Image Quality Gate**: Algorithmic validation of edge energy (blur) and luminance (lighting) prevents invalid capture.
4. **Server-Side Vision Inference**: Each quality-passed image is POSTed to `POST /v1/inference/analyze`; the backend adapter calls the hosted Roboflow model (`onion-yhzc7-mo9ib/1`, API key server-side only), validates the real response, and returns normalized predictions (top-left pixel boxes, verbatim class labels, real 0..1 confidence). Size estimator derives diameter from real box geometry + documented calibration.
5. **Batch Assessment (ONE final grade)**: 10–15 representative batch views are POSTed to `POST /v1/inference/batch-assess` with the grader-declared batch size; the backend runs Roboflow detection per image, builds structured evidence (view detections explicitly NOT unique onions — no double-counting), calls Qwen2.5-VL 72B via OpenRouter (`qwen/qwen2.5-vl-72b-instruct:free`) for batch visual assessment with a strict JSON schema, pins the declared count as the URS% denominator, and applies the deterministic OnionSetu batch policy (`v0.2-provisional`) to produce exactly ONE final grade: A, B, C, or Reject. The provider's grade field is a suggestion only and is re-validated, never trusted blindly.
6. **Confidence Gate**: If mean REAL model confidence < 70% — or the serving model provides no quality classes — flags for human verification. Roboflow detection confidence, provider assessment confidence, and the final grade decision are three separate concepts and are never averaged together.
6. **Grading Policy Engine**: Versioned rule calculates Grade A % and URS % from validated predictions only. The model never outputs percentages directly.
7. **Local Persistence & Sync**: Captures save to SQLite immediately as `pendingAi` (fully offline-safe); when online, inference runs, then results synchronize idempotently to PostgreSQL. A scan is never marked inference-complete unless Roboflow was actually called successfully.
8. **Digital Report & Audit**: Generates PDF with QR verification and registers SHA-256 hash-chain block.
9. **Disputes**: Farmer can file dispute with evidence; reviewer updates resolution in audit log.
