# backend/tests/test_batch_assess.py
"""Tests for POST /v1/inference/batch-assess.

Roboflow + OpenRouter adapters are monkeypatched — no test calls a real
provider. Covers: happy path, invalid suggestion, low confidence,
partial/all provider failures, auth, upload validation, audit trail,
and the A/B/C/Reject-only guarantee.
"""
import io

import pytest
from PIL import Image

from backend.app.services import openrouter_service as or_mod
from backend.app.services import roboflow_service as rf_mod
from backend.app.services.openrouter_service import OpenRouterAPIError, OpenRouterConfigError
from backend.app.services.roboflow_service import RoboflowAPIError


def _jpeg() -> bytes:
    img = Image.new("RGB", (96, 72), color=(190, 120, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _rf_result(count=25, mean_conf=0.93, classes=None):
    classes = classes or ["onion"]
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
                "confidence": mean_conf,
                "detection_id": f"det_{i}",
                "defect_type": "unknown",
                "quality_mapped": False,
            }
            for i in range(count)
        ],
        "observed_classes": classes,
        "quality_classification_available": False,
        "dropped_invalid_predictions": 0,
    }


def _provider_parsed(suggested="B", confidence=0.87, review=False, issues=None,
                     urs=12, assessed=150):
    from backend.app.schemas.batch import (
        BatchGradeEnum,
        BatchVisualAssessment,
        VisibleQualityIssue,
    )

    assessment = BatchVisualAssessment(
        batch_assessment="Mostly uniform batch.",
        observations=["Uniform bulbs"],
        visible_quality_issues=[
            VisibleQualityIssue(**i) for i in (issues or [])
        ],
        assessment_confidence=confidence,
        suggested_grade=BatchGradeEnum(suggested) if suggested else None,
        review_required=review,
        images_analyzed=2,
        # URS evidence: 12/150 = 8.0% -> band B unless overridden.
        urs_onions=urs,
        assessed_onions=assessed,
    )
    return {"assessment": assessment, "warnings": []}


async def _upload(client, token, n=10, files=None, assessed_onions=150):
    """POST a representative multi-view batch (default: 10 views, the
    minimum for a review-free assessment) with the grader-declared batch
    size (default 150, inside the required 100-200 range)."""
    if files is None:
        files = [("images", (f"view{i}.jpg", _jpeg(), "image/jpeg")) for i in range(n)]
    return await client.post(
        "/v1/inference/batch-assess",
        files=files,
        data={"assessed_onions": str(assessed_onions)},
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
async def test_batch_assess_happy_path_returns_one_final_grade(
    client, grader_token, monkeypatch
):
    async def fake_rf(image_bytes: bytes, client=None):
        return _rf_result()

    async def fake_provider(raw_images, evidence_summary, client=None):
        assert len(raw_images) == 10
        # Views depict the SAME physical batch: the summary must say view
        # detections are not unique onions (never summed as a batch count).
        assert "NOT unique onions" in evidence_summary
        return _provider_parsed()

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    res = await _upload(client, grader_token)
    assert res.status_code == 200
    body = res.json()
    assert body["final_grade"] == "B"
    assert body["assessment_confidence"] == 0.87
    assert body["sample_size"] == 250  # 25 view detections x 10 views
    assert body["sample_size_estimated"] is True
    assert body["images_analyzed"] == 10
    # URS% grounds the grade: 12 URS / 150 declared = 8.0% -> band B, and
    # the grader-declared denominator is echoed exactly.
    assert body["urs_percent"] == 8.0
    assert body["assessed_onions_declared"] == 150
    assert len(body["evidence"]) == 10
    # Clean suggestion + confident assessment: no review. (Roboflow's
    # onion-only labels do NOT force review here — the provider's visual
    # assessment is the quality layer in the batch pipeline.)
    assert body["review_required"] is False
    assert any("denominator" in r for r in body["review_reasons"])
    assert body["policy_version"].startswith("v0.2")
    assert body["roboflow_model"] == "onion-yhzc7-mo9ib/1"
    assert "qwen" in body["assessment_model"]
    assert "OPENROUTER_API_KEY" not in res.text
    assert "ROBOFLOW_API_KEY" not in res.text


@pytest.mark.asyncio
async def test_batch_assess_requires_auth(client):
    res = await client.post(
        "/v1/inference/batch-assess",
        files=[("images", ("v.jpg", _jpeg(), "image/jpeg"))],
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_batch_assess_rejects_empty_and_too_many(
    client, grader_token, monkeypatch
):
    async def fake_rf(image_bytes: bytes, client=None):
        return _rf_result(count=1)

    async def fake_provider(raw_images, evidence_summary, client=None):
        return _provider_parsed()

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    res = await client.post(
        "/v1/inference/batch-assess",
        files=[("images", ("v.jpg", b"", "image/jpeg"))],
        data={"assessed_onions": "150"},
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert res.status_code == 400

    too_many = [
        ("images", (f"v{i}.jpg", _jpeg(), "image/jpeg")) for i in range(16)
    ]
    res = await client.post(
        "/v1/inference/batch-assess",
        files=too_many,
        data={"assessed_onions": "150"},
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_batch_assess_all_roboflow_fail_is_502(
    client, grader_token, monkeypatch
):
    async def fake_rf(image_bytes: bytes, client=None):
        raise RoboflowAPIError("Roboflow returned HTTP 500")

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)

    res = await _upload(client, grader_token)
    assert res.status_code == 502


@pytest.mark.asyncio
async def test_batch_assess_partial_roboflow_failure_proceeds_with_review(
    client, grader_token, monkeypatch
):
    calls = {"n": 0}

    async def fake_rf(image_bytes: bytes, client=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RoboflowAPIError("Roboflow returned HTTP 500")
        return _rf_result(count=10)

    async def fake_provider(raw_images, evidence_summary, client=None):
        assert "FAILED" in evidence_summary
        return _provider_parsed()

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    res = await _upload(client, grader_token)
    assert res.status_code == 200
    body = res.json()
    assert body["sample_size"] == 90  # 10 views, first failed -> 9 x 10
    assert body["evidence"][0]["error"] is not None
    assert body["review_required"] is True
    assert any("partial evidence" in r for r in body["review_reasons"])


@pytest.mark.asyncio
async def test_batch_assess_provider_failure_is_502_not_fake_grade(
    client, grader_token, monkeypatch
):
    async def fake_rf(image_bytes: bytes, client=None):
        return _rf_result()

    async def fake_provider(raw_images, evidence_summary, client=None):
        raise OpenRouterAPIError("OpenRouter returned HTTP 500")

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    res = await _upload(client, grader_token)
    assert res.status_code == 502


@pytest.mark.asyncio
async def test_batch_assess_missing_provider_key_is_503(
    client, grader_token, monkeypatch
):
    async def fake_rf(image_bytes: bytes, client=None):
        return _rf_result()

    async def fake_provider(raw_images, evidence_summary, client=None):
        raise OpenRouterConfigError("OPENROUTER_API_KEY is not configured")

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    res = await _upload(client, grader_token)
    assert res.status_code == 503


@pytest.mark.asyncio
async def test_batch_assess_invalid_suggestion_falls_back_with_review(
    client, grader_token, monkeypatch
):
    async def fake_rf(image_bytes: bytes, client=None):
        return _rf_result()

    async def fake_provider(raw_images, evidence_summary, client=None):
        return _provider_parsed(suggested=None, urs=None, assessed=None)

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    res = await _upload(client, grader_token)
    assert res.status_code == 200
    body = res.json()
    assert body["final_grade"] == "Reject"  # configured provisional fallback
    assert body["review_required"] is True


@pytest.mark.asyncio
async def test_batch_assess_high_severity_caps_grade(
    client, grader_token, monkeypatch
):
    async def fake_rf(image_bytes: bytes, client=None):
        return _rf_result()

    async def fake_provider(raw_images, evidence_summary, client=None):
        return _provider_parsed(
            suggested="A",
            urs=3,
            assessed=150,
            issues=[{"issue": "Widespread rot", "severity": "high"}],
        )

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    res = await _upload(client, grader_token)
    assert res.status_code == 200
    body = res.json()
    assert body["final_grade"] == "C"
    assert body["review_required"] is True


@pytest.mark.asyncio
async def test_batch_assess_records_audit_event(
    client, grader_token, monkeypatch, db_session
):
    async def fake_rf(image_bytes: bytes, client=None):
        return _rf_result(count=5)

    async def fake_provider(raw_images, evidence_summary, client=None):
        return _provider_parsed()

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    res = await _upload(client, grader_token)
    assert res.status_code == 200

    audit_res = await client.get(
        "/v1/audit/verify",
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert audit_res.status_code == 200
    assert audit_res.json()["total_records_checked"] >= 1


@pytest.mark.asyncio
async def test_batch_assess_unknown_scan_is_404(client, grader_token):
    res = await client.post(
        "/v1/inference/batch-assess",
        files=[("images", ("v.jpg", _jpeg(), "image/jpeg"))],
        data={"scan_id": "does-not-exist", "assessed_onions": "150"},
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_batch_assess_low_confidence_forces_review(
    client, grader_token, monkeypatch
):
    async def fake_rf(image_bytes: bytes, client=None):
        return _rf_result(count=40)

    async def fake_provider(raw_images, evidence_summary, client=None):
        return _provider_parsed(suggested="A", confidence=0.31)

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    res = await client.post(
        "/v1/inference/batch-assess",
        files=[("images", ("v.jpg", _jpeg(), "image/jpeg"))],
        data={"assessed_onions": "150"},
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert res.status_code == 200
    body = res.json()
    # Grade still produced (exactly one), but flagged for human review —
    # uncertainty is never hidden inside a confident-looking grade.
    assert body["final_grade"] in ("A", "B", "C", "Reject")
    assert body["review_required"] is True
    assert any("below policy minimum" in r for r in body["review_reasons"])


@pytest.mark.asyncio
async def test_batch_assess_upstream_quota_passes_through_429(
    client, grader_token, monkeypatch
):
    from backend.app.services.openrouter_service import OpenRouterAPIError

    async def fake_rf(image_bytes: bytes, client=None):
        return _rf_result(count=5)

    async def fake_provider(raw_images, evidence_summary, client=None):
        raise OpenRouterAPIError(
            "OpenRouter returned HTTP 429: quota exceeded", upstream_status=429
        )

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    res = await client.post(
        "/v1/inference/batch-assess",
        files=[("images", ("v.jpg", _jpeg(), "image/jpeg"))],
        data={"assessed_onions": "150"},
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert res.status_code == 429


@pytest.mark.asyncio
async def test_batch_assess_with_scan_id_links_record(
    client, grader_token, monkeypatch
):
    # Create a scan first so the batch can attach to it.
    scan_payload = {
        "id": "scan-batch-01",
        "lot_number": "LOT-BATCH-01",
        "farmer_name": "Batch Farmer",
        "farmer_phone": "+919999900010",
        "procurement_center_id": "APMC-HQ-01",
        "grader_id": "grader_001",
    }
    created = await client.post(
        "/v1/scans/",
        json=scan_payload,
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert created.status_code == 201

    async def fake_rf(image_bytes: bytes, client=None):
        return _rf_result(count=5)

    async def fake_provider(raw_images, evidence_summary, client=None):
        return _provider_parsed()

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    res = await client.post(
        "/v1/inference/batch-assess",
        files=[("images", ("v.jpg", _jpeg(), "image/jpeg"))],
        data={"scan_id": "scan-batch-01", "assessed_onions": "150"},
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert res.status_code == 200

    report = await client.get(
        "/v1/reports/scan-batch-01/download",
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert report.status_code == 200
    assert report.headers["content-type"] == "application/pdf"
    assert len(report.content) > 1000


@pytest.mark.asyncio
async def test_batch_assess_requires_declared_batch_size(
    client, grader_token, monkeypatch
):
    """Missing/out-of-range assessed_onions -> 400, never a guessed grade."""
    async def fake_rf(image_bytes: bytes, client=None):
        return _rf_result()

    async def fake_provider(raw_images, evidence_summary, client=None):
        return _provider_parsed()

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    async def post(data):
        return await client.post(
            "/v1/inference/batch-assess",
            files=[("images", ("v.jpg", _jpeg(), "image/jpeg"))],
            data=data,
            headers={"Authorization": f"Bearer {grader_token}"},
        )

    assert (await post({})).status_code == 400
    assert (await post({"assessed_onions": "50"})).status_code == 400
    assert (await post({"assessed_onions": "250"})).status_code == 400
    assert (await post({"assessed_onions": "many"})).status_code in (400, 422)


@pytest.mark.asyncio
async def test_batch_assess_declared_boundaries_are_accepted(
    client, grader_token, monkeypatch
):
    """100 and 200 (the allowed range edges) are valid denominators."""
    from backend.app.schemas.batch import BatchGradeEnum, BatchVisualAssessment

    async def fake_rf(image_bytes: bytes, client=None):
        return _rf_result(count=5)

    def provider_for(urs):
        async def fake_provider(raw_images, evidence_summary, client=None):
            return {
                "assessment": BatchVisualAssessment(
                    batch_assessment="Boundary batch.",
                    observations=["Boundary"],
                    visible_quality_issues=[],
                    assessment_confidence=0.9,
                    suggested_grade=BatchGradeEnum.B,
                    review_required=False,
                    images_analyzed=len(raw_images),
                    urs_onions=urs,
                    assessed_onions=None,  # provider offers no denominator
                ),
                "warnings": [],
            }

        return fake_provider

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)

    monkeypatch.setattr(
        or_mod.OpenRouterService, "assess_batch", provider_for(urs=8)
    )
    res = await _upload(client, grader_token, assessed_onions=100)
    assert res.status_code == 200
    assert res.json()["assessed_onions_declared"] == 100
    assert res.json()["urs_percent"] == 8.0
    assert res.json()["review_required"] is False  # 8% -> B, suggestion agrees

    monkeypatch.setattr(
        or_mod.OpenRouterService, "assess_batch", provider_for(urs=12)
    )
    res = await _upload(client, grader_token, assessed_onions=200)
    assert res.status_code == 200
    assert res.json()["assessed_onions_declared"] == 200
    assert res.json()["urs_percent"] == 6.0


@pytest.mark.asyncio
async def test_batch_assess_fewer_than_min_views_forces_review(
    client, grader_token, monkeypatch
):
    """2 views still grade (fail loudly only on total evidence failure) but
    force human review — the set is not representative."""
    async def fake_rf(image_bytes: bytes, client=None):
        return _rf_result()

    async def fake_provider(raw_images, evidence_summary, client=None):
        return _provider_parsed()

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    res = await _upload(client, grader_token, n=2)
    assert res.status_code == 200
    body = res.json()
    assert body["final_grade"] == "B"  # exactly one grade, still produced
    assert body["review_required"] is True
    assert any("minimum" in r for r in body["review_reasons"])


@pytest.mark.asyncio
async def test_batch_assess_declared_denominator_wins_over_estimate(
    client, grader_token, monkeypatch
):
    """Provider estimate (150) vs grader-declared (120): declared is the
    denominator exactly, and the conflict forces human review."""
    async def fake_rf(image_bytes: bytes, client=None):
        return _rf_result()

    async def fake_provider(raw_images, evidence_summary, client=None):
        # urs=12 with declared 120 -> 10.0% -> band B (suggestion agrees,
        # so review comes ONLY from the denominator conflict).
        return _provider_parsed(suggested="B", urs=12, assessed=150)

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    res = await _upload(client, grader_token, assessed_onions=120)
    assert res.status_code == 200
    body = res.json()
    assert body["final_grade"] == "B"
    assert body["urs_percent"] == 10.0
    assert body["assessed_onions_declared"] == 120
    assert body["review_required"] is True
    assert any("differs" in r for r in body["review_reasons"])


@pytest.mark.asyncio
async def test_batch_assess_urs_above_declared_is_rejected(
    client, grader_token, monkeypatch
):
    """urs_onions > declared batch size is impossible evidence: rejected
    (never clamped), so the fallback grade + review apply."""
    async def fake_rf(image_bytes: bytes, client=None):
        return _rf_result()

    async def fake_provider(raw_images, evidence_summary, client=None):
        return _provider_parsed(suggested="A", urs=160, assessed=160)

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    res = await _upload(client, grader_token, assessed_onions=150)
    assert res.status_code == 200
    body = res.json()
    assert body["final_grade"] == "Reject"  # configured provisional fallback
    assert body["urs_percent"] is None
    assert body["assessed_onions_declared"] == 150
    assert body["review_required"] is True
    assert any("exceeds" in r for r in body["review_reasons"])
