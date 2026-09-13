# backend/tests/test_inference.py
"""Tests for POST /v1/inference/analyze.

The Roboflow adapter is monkeypatched — no test calls the real service.
Covers: success passthrough, auth requirement, empty upload rejection,
missing server key (503), and upstream failure mapping (502).
"""
import pytest

from backend.app.services import roboflow_service as rf_mod


def _adapter_result():
    return {
        "model_id": "onion-yhzc7-mo9ib/1",
        "image_width": 800,
        "image_height": 600,
        "predictions": [
            {
                "x": 100.0,
                "y": 100.0,
                "width": 120.0,
                "height": 100.0,
                "roboflow_class": "onion",
                "class_id": 0,
                "confidence": 0.93,
                "detection_id": "det_aaa",
                "defect_type": "unknown",
                "quality_mapped": False,
            }
        ],
        "observed_classes": ["onion"],
        "quality_classification_available": False,
        "dropped_invalid_predictions": 0,
    }


@pytest.mark.asyncio
async def test_analyze_success_returns_validated_predictions(
    client, grader_token, monkeypatch
):
    async def fake_analyze(image_bytes: bytes, client=None):
        assert len(image_bytes) > 0
        return _adapter_result()

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_analyze)

    res = await client.post(
        "/v1/inference/analyze",
        files={"image": ("scan_top.jpg", b"\xff\xd8\xfffake", "image/jpeg")},
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["model_id"] == "onion-yhzc7-mo9ib/1"
    assert len(body["predictions"]) == 1
    assert body["predictions"][0]["roboflow_class"] == "onion"
    assert body["predictions"][0]["confidence"] == 0.93
    assert body["quality_classification_available"] is False


@pytest.mark.asyncio
async def test_analyze_requires_auth(client):
    res = await client.post(
        "/v1/inference/analyze",
        files={"image": ("scan.jpg", b"\x00\x01", "image/jpeg")},
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_analyze_rejects_empty_upload(client, grader_token):
    res = await client.post(
        "/v1/inference/analyze",
        files={"image": ("scan.jpg", b"", "image/jpeg")},
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_analyze_rejects_non_image_upload(client, grader_token):
    res = await client.post(
        "/v1/inference/analyze",
        files={"image": ("notes.txt", b"hello", "text/plain")},
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_analyze_missing_server_key_is_503(client, grader_token, monkeypatch):
    async def fake_analyze(image_bytes: bytes, client=None):
        raise rf_mod.RoboflowConfigError("ROBOFLOW_API_KEY is not configured")

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_analyze)

    res = await client.post(
        "/v1/inference/analyze",
        files={"image": ("scan.jpg", b"\xff\xd8\xfffake", "image/jpeg")},
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert res.status_code == 503


@pytest.mark.asyncio
async def test_analyze_upstream_failure_is_502(client, grader_token, monkeypatch):
    async def fake_analyze(image_bytes: bytes, client=None):
        raise rf_mod.RoboflowAPIError("Roboflow returned HTTP 500")

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_analyze)

    res = await client.post(
        "/v1/inference/analyze",
        files={"image": ("scan.jpg", b"\xff\xd8\xfffake", "image/jpeg")},
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert res.status_code == 502


@pytest.mark.asyncio
async def test_analyze_records_audit_event(client, grader_token, monkeypatch, db_session):
    async def fake_analyze(image_bytes: bytes, client=None):
        return _adapter_result()

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_analyze)

    res = await client.post(
        "/v1/inference/analyze",
        files={"image": ("scan.jpg", b"\xff\xd8\xfffake", "image/jpeg")},
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert res.status_code == 200

    audit_res = await client.get(
        "/v1/audit/verify",
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert audit_res.status_code == 200
    assert audit_res.json()["total_records_checked"] >= 1


@pytest.mark.asyncio
async def test_analyze_upstream_quota_passes_through_429(client, grader_token, monkeypatch):
    async def fake_analyze(image_bytes: bytes, client=None):
        raise rf_mod.RoboflowAPIError('Roboflow returned HTTP 429: quota exceeded', upstream_status=429)

    monkeypatch.setattr(rf_mod.RoboflowService, 'analyze_image', fake_analyze)

    res = await client.post(
        '/v1/inference/analyze',
        files={'image': ('scan.jpg', b'\xff\xd8\xfffake', 'image/jpeg')},
        headers={'Authorization': f'Bearer {grader_token}'},
    )
    assert res.status_code == 429
