# OnionSetu: AI-Based Onion Quality Assessment System

OnionSetu is an offline-first mobile application and backend ecosystem designed to provide objective, transparent, and evidence-backed quality grading of onions at procurement centers. The product output is ONE final batch grade — **A / B / C / Reject** — produced by a deterministic policy over Roboflow detection evidence and Qwen2.5-VL 72B batch visual assessment via OpenRouter (per-image Grade A %/URS % remain as supporting evidence, not the product).

---

## 🏛️ System Architecture

- **Mobile Core (Flutter)**: Offline-first with guided 3-angle capture (Top, Side, Spread), OpenCV image quality gate (blur/lighting/framing), interactive bounding box visualization, and SQLite local storage.
- **Cloud Vision Pipeline (Roboflow)**: Hosted Roboflow vision model called server-side via FastAPI (`POST /v1/inference/analyze`, API key never leaves the server) for bounding boxes + classes with real confidence; deterministic size estimator in mm from real box geometry. Tested model returns `class = "onion"` — detection only, never treated as a grade.
- **Batch Assessment (Qwen2.5-VL 72B via OpenRouter + Deterministic Policy)**: Representative batch images + structured Roboflow evidence go to Qwen2.5-VL 72B server-side via OpenRouter (`POST /v1/inference/batch-assess`); the deterministic OnionSetu batch policy (`v0.1-provisional`) owns the ONE final A/B/C/Reject grade. AI confidences stay separate from the grade decision; low-confidence or uncertain batches go to human review.
- **Confidence Gate & Versioned Policy Engine**: AI confidence is strictly separated from grade outcomes; deterministic policy engines calculate results and flag borderline predictions for human review.
- **Backend API (FastAPI)**: REST endpoints for OTP/JWT authentication, scan ingestion, batch offline synchronization, disputes state machine, and admin command center.
- **Storage & Digital Certificates**: Automated ReportLab PDF certificates with QR code verification and Supabase storage integration.
- **Data Integrity**: Cryptographic SHA-256 tamper-evident hash-chain linking across all assessment and dispute records.

---

## 🚀 Quickstart & Local Development

### 1. Backend API & Dashboard
```bash
# Install Python dependencies
pip install -r backend/requirements.txt

# Run FastAPI Server
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Documentation: http://localhost:8000/docs
- Admin Dashboard: http://localhost:8000/static/admin/index.html

### 2. Frontend Flutter App
```bash
cd frontend
flutter pub get
flutter run
```

### 3. Docker Compose (Full Stack)
```bash
docker-compose up --build
```

### 4. Production Configuration (required for live AI)
Copy `.env.example` values into your gitignored local `.env` (never commit
real secrets), then set the deployment host:
```bash
OPENROUTER_API_KEY=<server-side only>
ROBOFLOW_API_KEY=<server-side only>
PUBLIC_BASE_URL=https://<deployed-host>
BATCH_POLICY_VERSION=v0.1-provisional
```
`docker-compose.yml` passes the local `.env` into the backend container
(`env_file`), so Roboflow + OpenRouter work inside Docker with zero committed
secrets. Without provider keys the AI endpoints honestly return `503`;
without quota they return `429` — never fake grades.

---

## 🧪 Automated Testing & Verification Suites

### Run All Frontend Tests (Flutter)
```bash
cd frontend
flutter test
```
*Coverage: Image quality validation gate, grading engine math, confidence gate, size estimator, ML preprocessing, NMS deduplication, and app navigation.*

### Run All Backend Tests (Pytest)
```bash
python -m pytest backend/tests -v
```
*Coverage: Health check, OTP auth, JWT verification, scan ingestion & pagination, ReportLab PDF report generation, dispute filing & reviewer resolution, batch offline sync, SHA-256 audit hash-chain tamper detection, Roboflow adapter, OpenRouter/Qwen adapter, batch A/B/C/Reject policy, and batch-assess endpoint.*

### Run Stress Benchmarks & End-to-End User Story
```bash
python scripts/benchmarks_and_stress_test.py
python scripts/e2e_user_story.py
```

---

## 📚 Documentation
- [Architecture Details](docs/ARCHITECTURE.md)
- [REST API Reference](docs/API.md)
- [Real-World Limitations](docs/LIMITATIONS.md)
- [115 Loops Execution Log](AGENT_PROGRESS.md)
