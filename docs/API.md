# OnionSetu: REST API Reference

Base URL: `http://localhost:8000/v1`

## Authentication
All protected routes require an HTTP Bearer JWT token in the `Authorization` header:
`Authorization: Bearer <JWT_ACCESS_TOKEN>`

### 1. Request OTP
- **POST** `/auth/send-otp`
- **Body**: `{"phone": "+91 98230 11223"}`
- **Response**: `{"status": "success", "message": "OTP sent successfully", "expires_in_seconds": 300}`

### 2. Verify OTP & Obtain Token
- **POST** `/auth/verify-otp`
- **Body**: `{"phone": "+91 98230 11223", "otp": "123456", "role": "grader", "name": "Ramesh Patil"}`
- **Response**: `{"access_token": "...", "token_type": "bearer", "expires_in": 7200, "user_id": "...", "role": "grader"}`

---

## AI Inference (Roboflow, server-side)

### 3a. Analyze Image via Hosted Vision Model
- **POST** `/inference/analyze` (multipart `image` file, Bearer JWT required)
- Forwards the image to the configured Roboflow Serverless model and returns
  VALIDATED predictions only. The Roboflow API key stays server-side
  (`ROBOFLOW_API_KEY` env); clients never see it.
- **Response**:
```json
{
  "model_id": "onion-yhzc7-mo9ib/1",
  "image_width": 800,
  "image_height": 600,
  "predictions": [
    {"x": 100.0, "y": 100.0, "width": 120.0, "height": 100.0,
     "roboflow_class": "onion", "class_id": 0, "confidence": 0.93,
     "detection_id": "det_aaa", "defect_type": "unknown",
     "quality_mapped": false}
  ],
  "observed_classes": ["onion"],
  "quality_classification_available": false,
  "dropped_invalid_predictions": 0
}
```
- Coordinates are top-left pixels in the submitted image. `roboflow_class`
  is the verbatim model label; `defect_type` is mapped only for known
  quality classes, else `unknown`. Every call is recorded in the SHA-256
  audit chain (`ROBOFLOW_INFERENCE`).
- Errors are truthful: `400` bad upload, `503` server key missing, `502`
  upstream/auth failure, `504` upstream timeout, `429` upstream quota
  exhaustion (passes through so clients fail fast instead of retrying).
  Failures must leave the
  scan `pendingAi`/`failed` for retry — never fake output.

### 3b. Batch Assessment: ONE Final Grade (A/B/C/Reject)
- **POST** `/inference/batch-assess` (multipart `images[]` files, 1–15,
  required `assessed_onions` form field = grader-declared physical batch
  size 100–200, optional `scan_id` form field, Bearer JWT required).
  Fewer than 10 views still grade but force human review (non-representative
  set); more than 15 views → `400`; missing/out-of-range `assessed_onions`
  → `400` (the denominator is never guessed).
- Backend pipeline per call: Roboflow detection per image → structured
  evidence → Qwen2.5-VL 72B batch visual assessment via OpenRouter →
  deterministic OnionSetu batch policy → exactly ONE final grade. Provider
  keys stay server-side; responses carry only model ids, never credentials.
- **Response**:
```json
{
  "final_grade": "B",
  "assessment_confidence": 0.87,
  "sample_size": 150,
  "sample_size_estimated": true,
  "images_analyzed": 10,
  "urs_percent": 8.0,
  "assessed_onions_declared": 150,
  "evidence": [{"image_index": 0, "detection_count": 22, "...": "..."}],
  "observations": ["Uniform bulbs across views"],
  "visible_quality_issues": [{"issue": "...", "severity": "low"}],
  "review_required": false,
  "review_reasons": ["Sample size is estimated."],
  "policy_version": "v0.1-provisional",
  "roboflow_model": "onion-yhzc7-mo9ib/1",
  "assessment_model": "qwen/qwen2.5-vl-72b-instruct:free",
  "batch_id": "...",
  "calculated_at": "..."
}
```
- `final_grade` is restricted to `A`/`B`/`C`/`Reject`. `assessment_confidence`
  is AI certainty — NOT a grade percentage. `sample_size` counts Roboflow
  view detections (NOT unique onions — the same physical batch appears in
  every view, so tallies are never summed as a batch count).
  `urs_percent` is the single URS% that grounded the grade
  (provider-estimated URS onions / grader-declared `assessed_onions_declared`
  × 100); `null` means URS evidence was unusable and the fallback grade
  applied. Every call is audit-logged
  (`BATCH_ASSESSED`); the row persists in `batch_assessments` and is
  included in the PDF report.

---

## Scans & Quality Assessments

### 3. Create / Upload Scan
- **POST** `/scans/`
- **Body**:
```json
{
  "id": "scan_uuid",
  "lot_number": "LOT-MH-8821",
  "farmer_name": "Suresh Shinde",
  "farmer_phone": "+91 98221 44556",
  "procurement_center_id": "APMC-LASALGAON-01",
  "grader_id": "grader_001",
  "images": [...],
  "detections": [...],
  "result": {
    "id": "res_uuid",
    "grade_a_percentage": 85.0,
    "urs_percentage": 15.0,
    "average_ai_confidence": 0.935,
    "policy_version": "v1.0.0",
    "total_onions_count": 20,
    "grade_a_count": 17,
    "damaged_count": 2,
    "rotten_count": 1,
    "sprouted_count": 0,
    "undersized_count": 0
  }
}
```

### 4. Retrieve Scan
- **GET** `/scans/{scan_id}`

### 5. Paginated Scans List & Search
- **GET** `/scans/?page=1&page_size=20&search=Suresh`

### 6. Generate & Download PDF Report
- **GET** `/reports/{scan_id}/download`
- **Returns**: `application/pdf` binary stream

---

## Synchronization

### 7. Batch Sync Offline Scans
- **POST** `/sync/batch`
- **Body**: `{"client_device_id": "tab_01", "scans": [...]}`

---

## Disputes & Auditing

### 8. File Dispute
- **POST** `/disputes/`
- **Body**: `{"scan_id": "scan_uuid", "reason": "...", "evidence_urls": [...]}`

### 9. Review / Resolve Dispute
- **PATCH** `/disputes/{dispute_id}`
- **Body**: `{"status": "upheld", "reviewer_notes": "...", "revised_grade_id": "..."}`

### 10. Verify Cryptographic SHA-256 Audit Chain
- **GET** `/audit/verify`
- **Response**: `{"is_valid": true, "total_records_checked": 100, "message": "All 100 audit records in chain verified successfully."}`

---

## Report Verification (QR target)

### 11. Verify a Scan Report (public, no auth)
- **GET** `/verify/{scan_id}`
- Backs the QR code printed on PDF reports, which encodes
  `{PUBLIC_BASE_URL}/v1/verify/{scan_id}`. Set `PUBLIC_BASE_URL` to the
  deployed host or printed QRs will not resolve outside localhost.
- Returns the lot/center, final batch grade, assessment confidence,
  estimated sample size, policy + model versions, audit hash, and
  chain validity. Contains NO personal data (no farmer/grader identity),
  so anyone scanning a report can verify it.
- `final_grade` is `null` when no validated batch assessment exists yet;
  unknown ids return `404`.
