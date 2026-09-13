# backend/tests/test_verify.py
"""Tests for the public report verification endpoint (QR target).

GET /v1/verify/{scan_id} requires NO auth (anyone scanning a printed
report must reach it) and returns NO personal data.
"""
import pytest


@pytest.mark.asyncio
async def test_verify_scan_with_batch_grade(client, grader_token, monkeypatch):
    from backend.app.services import openrouter_service as or_mod
    from backend.app.services import roboflow_service as rf_mod

    scan_payload = {
        "id": "scan-verify-01",
        "lot_number": "LOT-VER-01",
        "farmer_name": "Private Farmer",
        "farmer_phone": "+919999900099",
        "procurement_center_id": "APMC-VER-01",
        "grader_id": "grader_001",
    }
    created = await client.post(
        "/v1/scans/",
        json=scan_payload,
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert created.status_code == 201

    async def fake_rf(image_bytes: bytes, client=None):
        return {
            "model_id": "onion-yhzc7-mo9ib/1",
            "image_width": 100,
            "image_height": 100,
            "predictions": [
                {
                    "x": 10.0, "y": 10.0, "width": 20.0, "height": 20.0,
                    "roboflow_class": "onion", "class_id": 0,
                    "confidence": 0.97, "detection_id": "d1",
                    "defect_type": "unknown", "quality_mapped": False,
                }
            ],
            "observed_classes": ["onion"],
            "quality_classification_available": False,
            "dropped_invalid_predictions": 0,
        }

    async def fake_provider(raw_images, evidence_summary, client=None):
        from backend.app.schemas.batch import (
            BatchGradeEnum, BatchVisualAssessment,
        )
        return {
            "assessment": BatchVisualAssessment(
                batch_assessment="Uniform batch.",
                observations=["Uniform"],
                visible_quality_issues=[],
                assessment_confidence=0.9,
                suggested_grade=BatchGradeEnum.B,
                review_required=False,
                images_analyzed=1,
                urs_onions=12,
                assessed_onions=150,
            ),
            "warnings": [],
        }

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    assessed = await client.post(
        "/v1/inference/batch-assess",
        files=[("images", ("v.jpg", b"\xff\xd8\xfffake", "image/jpeg"))],
        data={"scan_id": "scan-verify-01", "assessed_onions": "150"},
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert assessed.status_code == 200

    # Public: no Authorization header at all.
    res = await client.get("/v1/verify/scan-verify-01")
    assert res.status_code == 200
    body = res.json()
    assert body["scan_id"] == "scan-verify-01"
    assert body["lot_number"] == "LOT-VER-01"
    assert body["final_grade"] == "B"
    assert body["chain_valid"] is True
    # URS driver is public on the verification payload (12/150 = 8.0%).
    assert body["urs_percent"] == 8.0
    assert body["assessed_onions_declared"] == 150
    # Non-PII guarantee: personal data must never appear here.
    blob = res.text
    assert "Private Farmer" not in blob
    assert "+919999900099" not in blob
    assert "grader_001" not in blob


@pytest.mark.asyncio
async def test_verify_scan_without_batch_grade(client, grader_token):
    await client.post(
        "/v1/scans/",
        json={
            "id": "scan-verify-02",
            "lot_number": "LOT-VER-02",
            "farmer_name": "N",
            "farmer_phone": "+910000000000",
            "procurement_center_id": "APMC-VER-01",
            "grader_id": "grader_001",
        },
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    res = await client.get("/v1/verify/scan-verify-02")
    assert res.status_code == 200
    assert res.json()["final_grade"] is None
    assert res.json()["chain_valid"] is True


@pytest.mark.asyncio
async def test_verify_unknown_scan_is_404(client):
    res = await client.get("/v1/verify/does-not-exist")
    assert res.status_code == 404


def test_qr_url_resolves_to_configured_verify_endpoint(monkeypatch):
    from backend.app.services import report_service as rep_mod

    monkeypatch.setattr(
        rep_mod.settings, "PUBLIC_BASE_URL", "https://demo.onionsetu.org/"
    )
    url = rep_mod.build_verification_url("scan-abc-123")
    assert url == "https://demo.onionsetu.org/v1/verify/scan-abc-123"
    assert "onionsetu.org/verify/" not in url  # dead legacy link is gone
