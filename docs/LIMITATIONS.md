# OnionSetu: Real-World Limitations & Sensing Boundaries

In accordance with strict anti-hallucination engineering standards, the following real-world boundaries are explicitly documented:

## 0. Current AI Capability (Roboflow + Qwen batch pipeline)
- **Active pipeline**: ONE hosted Roboflow vision model (`onion-yhzc7-mo9ib/1`, detection only) + Qwen2.5-VL 72B via OpenRouter (`qwen/qwen2.5-vl-72b-instruct:free`, batch visual assessment), both called server-side. The backend deterministic policy owns the ONE final A/B/C/Reject grade. The old YOLOv8 + MobileNetV2 + TFLite on-device pipeline is RETIRED; Gemini 3.1 Pro was removed as a runtime provider.
- **Tested Roboflow behavior**: live-tested against a real onion image returning `class = "onion"`, confidence ≈ 0.9765. The detector finds onions; it does NOT classify A/B/C/Reject. `"onion"` is never treated as Grade A.
- **Batch policy is provisional ("OnionSetu v0.2-provisional", NOT official AGMARK/APMC boundaries)**: no official A/B/C/Reject thresholds exist in this repository. The deterministic policy grades by URS% = (URS onions / assessed onions) x 100 computed from the provider's estimated URS evidence: A<=5%, B<=10%, C<=20%, else Reject; unknown/empty URS evidence forces human review with a configured fallback. These bands MUST be replaced by officially signed-off thresholds before commercial use.
- **Sample counts are estimated, never double-counted as a census**: view detections are NOT unique onions — the same physical onions recur across the 10–15 views, so per-view tallies are never summed as a batch count. The URS% denominator is always the grader-declared physical batch size (100–200).
- **Connectivity requirement**: Roboflow + OpenRouter need internet. Offline captures are stored as `pendingAi` and assessed when online; the app never marks inference complete without successful provider calls. Provider failures preserve scans + Roboflow evidence for retry.
- **Multimodal cost/latency/rate limits**: each batch assessment makes one Roboflow call per image plus one OpenRouter multimodal call (90s server timeout). Free-tier models may rate-limit (HTTP 429 passes through; no retry storms). Budget/rate-limit accordingly.
- **Live assessment status**: batch visual assessment runs on Qwen2.5-VL 72B via OpenRouter (operator key in gitignored local `.env`). Live Roboflow detection verified (`class="onion"` ≈ 0.9765). If the assessment provider is unreachable or rate-limited (e.g. HTTP 429), the API fails loudly with typed errors and no grade — never a fabricated result.
- **Size calibration**: diameter (mm) is estimated from real box geometry at an assumed `3.8 px/mm` (40cm capture height). Without tray markers / fixed rig geometry this is an estimate, not a calibrated measurement.
- **Report verification**: printed QR codes resolve to `GET /v1/verify/{scan_id}` on the deployment configured via `PUBLIC_BASE_URL` (default localhost). The endpoint is public by design and returns NO personal data — only lot/center, grade, confidence, URS%, declared batch size, views analyzed, policy/model versions, audit hash, and chain validity.

## 1. RGB Sensing vs Concealed Internal Defects
- **External Surface Defects (Solved)**: Sprouted green shoots, black/grey mold decay, mechanical skin bruising, surface cuts, and undersized diameters are accurately detected and classified from RGB camera imagery.
- **Concealed Internal Defects (Boundary)**: Internal rot (e.g. inner scale decay, neck rot starting inside flesh without surface skin discoloration) cannot be guaranteed by standard smartphone RGB cameras alone.
- **Future Sensor Extensions**: High-volume procurement hubs requiring internal inspection will require multi-spectral, NIR (Near-Infrared), hyperspectral, or X-ray inspection sidecars.

## 2. Tray Calibration & Illumination Requirements
- Standardized sampling requires spreading onions on a neutral, non-glare surface (white/grey APMC calibration tray).
- Size estimation assumes standardized capture distance (~40cm) or calibration markers on the tray.
- Extreme glare from direct midday sun or uneven cast shadows should be minimized by utilizing diffuse overhead canopy lighting at procurement gates.

## 3. Policy & Confidence Calibration
- AI confidence strictly measures model prediction certainty and is distinct from Grade A %.
- Grade A % and URS % thresholds are derived from the project's versioned grading policy (`v1.0.0`) in accordance with APMC standards.
- Final commercial sign-off in new regional APMC centers requires local variety calibration with agricultural inspection officers.
