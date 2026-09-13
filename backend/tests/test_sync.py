# backend/tests/test_sync.py
import pytest

@pytest.mark.asyncio
async def test_batch_sync_offline_scans(client, grader_token):
    batch_payload = {
        "client_device_id": "tablet_lasalgaon_04",
        "scans": [
            {
                "id": "scan_offline_sync_01",
                "lot_number": "LOT-SYNC-01",
                "farmer_name": "Deepak Jadhav",
                "farmer_phone": "+919811223344",
                "procurement_center_id": "APMC-LASALGAON-01",
                "grader_id": "grader_001",
                "sync_status": "pendingOffline",
                "result": {
                    "id": "res_sync_01",
                    "grade_a_percentage": 90.0,
                    "urs_percentage": 10.0,
                    "average_ai_confidence": 0.95,
                    "total_onions_count": 10,
                    "grade_a_count": 9,
                    "damaged_count": 1,
                    "rotten_count": 0,
                    "sprouted_count": 0,
                    "undersized_count": 0,
                }
            },
            {
                "id": "scan_offline_sync_02",
                "lot_number": "LOT-SYNC-02",
                "farmer_name": "Vijay Deshmukh",
                "farmer_phone": "+919822334455",
                "procurement_center_id": "APMC-LASALGAON-01",
                "grader_id": "grader_001",
                "sync_status": "pendingOffline",
            }
        ]
    }

    sync_res = await client.post(
        "/v1/sync/batch",
        json=batch_payload,
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert sync_res.status_code == 200
    sync_data = sync_res.json()
    assert sync_data["processed_count"] == 2
    assert "scan_offline_sync_01" in sync_data["synced_ids"]
    assert "scan_offline_sync_02" in sync_data["synced_ids"]

    # Verify repeated sync is idempotent and does not error
    repeat_res = await client.post(
        "/v1/sync/batch",
        json=batch_payload,
        headers={"Authorization": f"Bearer {grader_token}"},
    )
    assert repeat_res.status_code == 200
    assert repeat_res.json()["processed_count"] == 2
