# backend/tests/test_reports.py
import pytest

@pytest.mark.asyncio
async def test_generate_and_download_pdf_report(client, grader_token):
    # Create scan first
    scan_payload = {
        "id": "scan_report_test_01",
        "lot_number": "LOT-REP-9001",
        "farmer_name": "Narayan Kadam",
        "farmer_phone": "+919877665544",
        "procurement_center_id": "APMC-SOLAPUR-03",
        "grader_id": "grader_001",
        "sync_status": "synced",
        "result": {
            "id": "res_rep_01",
            "grade_a_percentage": 85.0,
            "urs_percentage": 15.0,
            "average_ai_confidence": 0.91,
            "confidence_status": "highConfidence",
            "policy_version": "v1.0.0",
            "total_onions_count": 20,
            "grade_a_count": 17,
            "damaged_count": 2,
            "rotten_count": 1,
            "sprouted_count": 0,
            "undersized_count": 0,
            "avg_size_mm": 54.5,
            "audit_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        },
    }
    await client.post("/v1/scans/", json=scan_payload, headers={"Authorization": f"Bearer {grader_token}"})

    # Download PDF Report
    res = await client.get("/v1/reports/scan_report_test_01/download", headers={"Authorization": f"Bearer {grader_token}"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert len(res.content) > 1000 # Valid PDF payload size
    assert res.content.startswith(b"%PDF")
