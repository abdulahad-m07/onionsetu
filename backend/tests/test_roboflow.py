# backend/tests/test_roboflow.py
"""Unit tests for the Roboflow server-side adapter.

All HTTP is mocked via httpx.MockTransport — no test calls the real
Roboflow service, and no fake model files are involved.
"""
import base64
import json

import httpx
import pytest

from backend.app.services import roboflow_service as rf_mod
from backend.app.services.roboflow_service import (
    RoboflowAPIError,
    RoboflowAuthError,
    RoboflowConfigError,
    RoboflowResponseError,
    RoboflowService,
    RoboflowTimeoutError,
)

FAKE_JPEG = b"\xff\xd8\xfffake-jpeg-bytes"


@pytest.fixture(autouse=True)
def _dummy_server_key(monkeypatch):
    # Adapter tests must never depend on a real key; the missing-key case
    # overrides this per-test. monkeypatch auto-restores afterwards.
    monkeypatch.setattr(rf_mod.settings, "ROBOFLOW_API_KEY", "test-key")


def _ok_payload():
    return {
        "predictions": [
            {
                "x": 160.0,
                "y": 150.0,
                "width": 120.0,
                "height": 100.0,
                "class": "onion",
                "class_id": 0,
                "confidence": 0.93,
                "detection_id": "det_aaa",
            },
            {
                "x": 400.0,
                "y": 300.0,
                "width": 80.0,
                "height": 90.0,
                "class": "gradeA",
                "class_id": 1,
                "confidence": 0.88,
                "detection_id": "det_bbb",
            },
            # Malformed entry: must be skipped + counted, never fixed up.
            {"x": 1.0, "class": "onion"},
        ],
        "image": {"width": 800, "height": 600},
    }


def _mock_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_request_construction_uses_server_key_and_base64(monkeypatch):
    monkeypatch.setattr(rf_mod.settings, "ROBOFLOW_API_KEY", "server-secret")
    monkeypatch.setattr(rf_mod.settings, "ROBOFLOW_MODEL_ID", "onion-yhzc7-mo9ib/1")
    monkeypatch.setattr(
        rf_mod.settings, "ROBOFLOW_API_URL", "https://serverless.roboflow.com"
    )

    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["content_type"] = request.headers.get("content-type")
        seen["body"] = request.content
        return httpx.Response(200, json=_ok_payload())

    result = await RoboflowService.analyze_image(
        FAKE_JPEG, client=_mock_client(handler)
    )

    assert "serverless.roboflow.com/onion-yhzc7-mo9ib/1" in seen["url"]
    assert "api_key=server-secret" in seen["url"]
    assert "confidence=" in seen["url"] and "overlap=" in seen["url"]
    assert "server-secret" not in seen["body"].decode()
    assert base64.b64decode(seen["body"]) == FAKE_JPEG
    assert "x-www-form-urlencoded" in seen["content_type"]
    assert len(result["predictions"]) == 2


@pytest.mark.asyncio
async def test_successful_response_parsing_center_to_corner():
    def handler(request: httpx.Request):
        return httpx.Response(200, json=_ok_payload())

    result = await RoboflowService.analyze_image(
        FAKE_JPEG, client=_mock_client(handler)
    )

    assert result["model_id"] == "onion-yhzc7-mo9ib/1"
    assert result["image_width"] == 800
    assert result["image_height"] == 600
    assert result["dropped_invalid_predictions"] == 1

    first, second = result["predictions"]
    # Center (160,150) w=120 h=100 -> top-left (100,100).
    assert first["x"] == pytest.approx(100.0)
    assert first["y"] == pytest.approx(100.0)
    assert first["confidence"] == pytest.approx(0.93)
    # Unknown detector label passes through verbatim, never mapped.
    assert first["roboflow_class"] == "onion"
    assert first["defect_type"] == "unknown"
    assert first["quality_mapped"] is False
    # Known quality label maps.
    assert second["roboflow_class"] == "gradeA"
    assert second["defect_type"] == "gradeA"
    assert second["quality_mapped"] is True

    assert result["observed_classes"] == ["gradeA", "onion"]
    # Mixed known/unknown -> quality classification NOT available.
    assert result["quality_classification_available"] is False


@pytest.mark.asyncio
async def test_all_quality_classes_available_flag():
    payload = {
        "predictions": [
            {
                "x": 10.0,
                "y": 10.0,
                "width": 20.0,
                "height": 20.0,
                "class": "rotten",
                "confidence": 0.9,
            }
        ],
        "image": {"width": 100, "height": 100},
    }

    def handler(request: httpx.Request):
        return httpx.Response(200, json=payload)

    result = await RoboflowService.analyze_image(
        FAKE_JPEG, client=_mock_client(handler)
    )
    assert result["quality_classification_available"] is True
    assert result["predictions"][0]["defect_type"] == "rotten"


@pytest.mark.asyncio
async def test_malformed_response_missing_predictions():
    def handler(request: httpx.Request):
        return httpx.Response(200, json={"image": {}})

    with pytest.raises(RoboflowResponseError):
        await RoboflowService.analyze_image(FAKE_JPEG, client=_mock_client(handler))


@pytest.mark.asyncio
async def test_malformed_response_non_json():
    def handler(request: httpx.Request):
        return httpx.Response(200, content=b"not json{{{")

    with pytest.raises(RoboflowResponseError):
        await RoboflowService.analyze_image(FAKE_JPEG, client=_mock_client(handler))


@pytest.mark.asyncio
async def test_api_failure_status():
    def handler(request: httpx.Request):
        return httpx.Response(500, text="upstream exploded")

    with pytest.raises(RoboflowAPIError):
        await RoboflowService.analyze_image(FAKE_JPEG, client=_mock_client(handler))


@pytest.mark.asyncio
async def test_auth_failure_status():
    for code in (401, 403):
        def handler(request: httpx.Request, _code=code):
            return httpx.Response(_code, json={"status": _code})

        with pytest.raises(RoboflowAuthError):
            await RoboflowService.analyze_image(
                FAKE_JPEG, client=_mock_client(handler)
            )


@pytest.mark.asyncio
async def test_timeout_maps_to_timeout_error():
    def handler(request: httpx.Request):
        raise httpx.ConnectTimeout("slow upstream")

    with pytest.raises(RoboflowTimeoutError):
        await RoboflowService.analyze_image(FAKE_JPEG, client=_mock_client(handler))


@pytest.mark.asyncio
async def test_missing_api_key_never_hits_network(monkeypatch):
    monkeypatch.setattr(rf_mod.settings, "ROBOFLOW_API_KEY", "")

    def handler(request: httpx.Request):
        raise AssertionError("network must not be touched without a key")

    with pytest.raises(RoboflowConfigError):
        await RoboflowService.analyze_image(FAKE_JPEG, client=_mock_client(handler))


@pytest.mark.asyncio
async def test_empty_image_rejected():
    def handler(request: httpx.Request):  # pragma: no cover
        raise AssertionError("unreachable")

    with pytest.raises(RoboflowResponseError):
        await RoboflowService.analyze_image(b"", client=_mock_client(handler))


@pytest.mark.asyncio
async def test_confidence_out_of_range_prediction_dropped():
    payload = {
        "predictions": [
            {
                "x": 10.0,
                "y": 10.0,
                "width": 20.0,
                "height": 20.0,
                "class": "onion",
                "confidence": 9.9,  # impossible: must not become output
            }
        ],
        "image": {"width": 100, "height": 100},
    }

    def handler(request: httpx.Request):
        return httpx.Response(200, json=payload)

    result = await RoboflowService.analyze_image(
        FAKE_JPEG, client=_mock_client(handler)
    )
    assert result["predictions"] == []
    assert result["dropped_invalid_predictions"] == 1
    assert result["quality_classification_available"] is False
