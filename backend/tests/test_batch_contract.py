# backend/tests/test_batch_contract.py
"""Contract + idempotency guarantees for the batch pipeline.

- The batch response schema exposes exactly ONE grade (no per-onion
  grades, no A/B/C percentages anywhere in the contract).
- Repeated sync of the same batch assessment never duplicates rows.
- Report generation succeeds with and without a batch attached.
"""
import pytest
from sqlalchemy.future import select

from backend.app.models.batch import BatchAssessment
from backend.app.schemas.batch import BatchAssessResponse


def test_response_contract_has_exactly_one_grade():
    fields = set(BatchAssessResponse.model_fields)
    assert "final_grade" in fields
    for forbidden in (
        "per_onion_grades",
        "item_grades",
        "grade_a_share",
        "grade_b_share",
        "grade_c_share",
        "reject_share",
        "grade_percentages",
        "onion_grades",
    ):
        assert forbidden not in fields, f"contract must not contain {forbidden}"
    # Evidence items carry detection evidence only — verified structurally:
    from backend.app.schemas.batch import RoboflowImageEvidence

    evidence_fields = set(RoboflowImageEvidence.model_fields)
    assert "final_grade" not in evidence_fields
    assert "grade" not in evidence_fields
    # The batch contract exposes the URS driver explicitly (the single URS%
    # that grounded the grade + the grader-declared denominator) — still
    # exactly ONE grade, never per-grade percentages.
    assert "urs_percent" in fields
    assert "assessed_onions_declared" in fields


@pytest.mark.asyncio
async def test_duplicate_batch_sync_is_idempotent(
    client, grader_token, db_session
):
    scan_payload = {
        "id": "scan-dup-01",
        "lot_number": "LOT-DUP-01",
        "farmer_name": "Dup Farmer",
        "farmer_phone": "+919999900011",
        "procurement_center_id": "APMC-DUP-01",
        "grader_id": "grader_001",
        "batch_assessment": {
            "id": "batch-dup-01",
            "scan_id": "scan-dup-01",
            "status": "completed",
            "final_grade": "B",
            "assessment_confidence": 0.87,
            "sample_size": 150,
            "sample_size_estimated": True,
            "images_analyzed": 3,
            "review_required": False,
            "policy_version": "v0.1-provisional",
            "roboflow_model": "onion-yhzc7-mo9ib/1",
            "assessment_model": "qwen/qwen2.5-vl-72b-instruct:free",
        },
    }
    body = {"client_device_id": "tab_dup", "scans": [scan_payload]}
    headers = {"Authorization": f"Bearer {grader_token}"}

    first = await client.post("/v1/sync/batch", json=body, headers=headers)
    assert first.status_code == 200
    second = await client.post("/v1/sync/batch", json=body, headers=headers)
    assert second.status_code == 200
    assert second.json()["processed_count"] == 1

    rows = (
        (await db_session.execute(select(BatchAssessment))).scalars().all()
    )
    assert len([r for r in rows if r.id == "batch-dup-01"]) == 1


@pytest.mark.asyncio
async def test_report_with_batch_attached_renders_pdf(
    client, grader_token, monkeypatch
):
    from backend.app.services import openrouter_service as or_mod
    from backend.app.services import roboflow_service as rf_mod
    from backend.app.schemas.batch import BatchGradeEnum, BatchVisualAssessment

    await client.post(
        "/v1/scans/",
        json={
            "id": "scan-rep-batch-01",
            "lot_number": "LOT-REP-B-01",
            "farmer_name": "Rep Farmer",
            "farmer_phone": "+919999900012",
            "procurement_center_id": "APMC-REP-01",
            "grader_id": "grader_001",
        },
        headers={"Authorization": f"Bearer {grader_token}"},
    )

    async def fake_rf(image_bytes: bytes, client=None):
        return {
            "model_id": "onion-yhzc7-mo9ib/1",
            "image_width": 100, "image_height": 100,
            "predictions": [],
            "observed_classes": [],
            "quality_classification_available": False,
            "dropped_invalid_predictions": 0,
        }

    async def fake_provider(raw_images, evidence_summary, client=None):
        return {
            "assessment": BatchVisualAssessment(
                batch_assessment="Empty tray views.",
                observations=["No onions visible"],
                visible_quality_issues=[],
                assessment_confidence=0.99,
                suggested_grade=BatchGradeEnum.REJECT,
                review_required=True,
                images_analyzed=1,
            ),
            "warnings": [],
        }

    monkeypatch.setattr(rf_mod.RoboflowService, "analyze_image", fake_rf)
    monkeypatch.setattr(or_mod.OpenRouterService, "assess_batch", fake_provider)

    assessed = await client.post(
        "/v1/inference/batch-assess",
        files=[("images", ("v.jpg", b"\xff\xd8\xfffake", "image/jpeg"))],
        data={"scan_id": "scan-rep-batch-01", "assessed_onions": "150"},
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert assessed.status_code == 200
    assert assessed.json()["final_grade"] == "Reject"

    pdf = await client.get(
        "/v1/reports/scan-rep-batch-01/download",
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert len(pdf.content) > 1000
