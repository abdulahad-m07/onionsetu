# backend/tests/test_disputes.py
import pytest

@pytest.mark.asyncio
async def test_dispute_workflow_and_review(client, farmer_token, grader_token):
    # 1. Create base scan
    scan_id = "scan_disp_test_01"
    scan_payload = {
        "id": scan_id,
        "lot_number": "LOT-DISP-001",
        "farmer_name": "Suresh Shinde",
        "farmer_phone": "+919999900003",
        "procurement_center_id": "APMC-LASALGAON-01",
        "grader_id": "grader_001",
        "sync_status": "synced",
    }
    await client.post("/v1/scans/", json=scan_payload, headers={"Authorization": f"Bearer {grader_token}"})

    # 2. Farmer files dispute
    disp_res = await client.post(
        "/v1/disputes/",
        json={
            "scan_id": scan_id,
            "reason": "Grade A percentage is too low; onions were harvested fresh yesterday.",
            "evidence_urls": ["https://storage.onionsetu.org/disp1.jpg"],
        },
        headers={"Authorization": f"Bearer {farmer_token}"},
    )
    assert disp_res.status_code == 201
    disp_data = disp_res.json()
    assert disp_data["status"] == "pendingReview"
    dispute_id = disp_data["id"]

    # 3. Grader/Officer reviews and resolves dispute
    update_res = await client.patch(
        f"/v1/disputes/{dispute_id}",
        json={
            "status": "upheld",
            "reviewer_notes": "Re-inspected under calibration illumination. Revised Grade A to 88%.",
            "revised_grade_id": "rev_grade_002",
        },
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "upheld"
    assert update_res.json()["reviewer_notes"] is not None
