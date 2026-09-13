# backend/tests/test_audit.py
import pytest
from sqlalchemy.future import select
from backend.app.models.audit import AuditLog
from backend.app.services.audit_service import AuditService

@pytest.mark.asyncio
async def test_audit_hash_chain_integrity_and_tamper_detection(db_session, client, grader_token):
    # 1. Record series of valid audit events
    await AuditService.record_event(
        db=db_session,
        action="SCAN_CREATED",
        entity_type="Scan",
        entity_id="scan_audit_01",
        actor_id="grader_001",
        payload={"lot_number": "LOT-AUDIT-01", "grade_a": 85.0},
    )
    await AuditService.record_event(
        db=db_session,
        action="GRADE_CALCULATED",
        entity_type="GradingResult",
        entity_id="res_audit_01",
        actor_id="grader_001",
        payload={"grade_a_percentage": 85.0, "urs_percentage": 15.0},
    )
    await AuditService.record_event(
        db=db_session,
        action="DISPUTE_FILED",
        entity_type="Dispute",
        entity_id="disp_audit_01",
        actor_id="farmer_001",
        payload={"reason": "Farmer review request"},
    )
    await db_session.commit()

    # 2. Verify chain passes via API
    verify_res = await client.get("/v1/audit/verify", headers={"Authorization": f"Bearer {grader_token}"})
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert verify_data["is_valid"] is True
    assert verify_data["total_records_checked"] == 3

    # 3. Simulate unauthorized database record tampering
    result = await db_session.execute(select(AuditLog).where(AuditLog.entity_id == "res_audit_01"))
    record_to_tamper = result.scalar_one()
    # Malicious actor changes payload without valid cryptographic re-hashing
    record_to_tamper.payload_json = '{"grade_a_percentage": 99.9, "urs_percentage": 0.1}'
    await db_session.commit()

    # 4. Verify chain fails and detects tamper
    tamper_res = await client.get("/v1/audit/verify", headers={"Authorization": f"Bearer {grader_token}"})
    assert tamper_res.status_code == 200
    tamper_data = tamper_res.json()
    assert tamper_data["is_valid"] is False
    assert "Tampered" in tamper_data["message"]
