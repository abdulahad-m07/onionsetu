# backend/tests/test_scans.py
import pytest

@pytest.mark.asyncio
async def test_create_and_retrieve_scan(client, grader_token):
    scan_payload = {
        "id": "scan_test_uuid_101",
        "lot_number": "LOT-MH-5501",
        "farmer_name": "Bhaskar Rao",
        "farmer_phone": "+919822114455",
        "procurement_center_id": "APMC-LASALGAON-01",
        "grader_id": "grader_001",
        "sync_status": "synced",
        "images": [
            {
                "id": "img_001",
                "local_path": "/data/images/scan_101_top.jpg",
                "angle": "topView",
                "quality_passed": True,
            }
        ],
        "detections": [
            {
                "id": "det_001",
                "x": 100.0,
                "y": 100.0,
                "width": 120.0,
                "height": 120.0,
                "defect_type": "gradeA",
                "confidence": 0.94,
                "estimated_diameter_mm": 58.0,
            }
        ],
        "result": {
            "id": "res_001",
            "grade_a_percentage": 100.0,
            "urs_percentage": 0.0,
            "average_ai_confidence": 0.94,
            "confidence_status": "highConfidence",
            "policy_version": "v1.0.0",
            "total_onions_count": 1,
            "grade_a_count": 1,
            "damaged_count": 0,
            "rotten_count": 0,
            "sprouted_count": 0,
            "undersized_count": 0,
            "avg_size_mm": 58.0,
            "audit_hash": "a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890",
        },
    }

    # 1. Submit Scan
    create_res = await client.post(
        "/v1/scans/",
        json=scan_payload,
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["id"] == "scan_test_uuid_101"
    assert created_data["lot_number"] == "LOT-MH-5501"
    assert len(created_data["images"]) == 1
    assert len(created_data["detections"]) == 1
    assert created_data["result"]["grade_a_percentage"] == 100.0

    # 2. Retrieve Scan by ID
    get_res = await client.get(
        "/v1/scans/scan_test_uuid_101",
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert get_res.status_code == 200
    assert get_res.json()["farmer_name"] == "Bhaskar Rao"

    # 3. List Scans with Pagination & Search
    list_res = await client.get(
        "/v1/scans/?search=Bhaskar",
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert len(list_data["items"]) >= 1
