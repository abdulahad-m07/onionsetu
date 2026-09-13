# backend/app/services/audit_service.py
import json
import hashlib
from datetime import datetime
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.models.audit import AuditLog

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

class AuditService:
    @staticmethod
    def calculate_hash(prev_hash: str, payload_json: str, timestamp_iso: str) -> str:
        data_to_hash = f"{prev_hash}:{payload_json}:{timestamp_iso}"
        return hashlib.sha256(data_to_hash.encode("utf-8")).hexdigest()

    @staticmethod
    async def record_event(
        db: AsyncSession,
        action: str,
        entity_type: str,
        entity_id: str,
        actor_id: str,
        payload: dict,
    ) -> AuditLog:
        # Get the latest audit log entry to extract previous hash
        result = await db.execute(
            select(AuditLog).order_by(AuditLog.sequence_number.desc()).limit(1)
        )
        last_entry = result.scalar_one_or_none()

        prev_hash = last_entry.current_hash if last_entry else GENESIS_HASH
        created_at = datetime.utcnow()
        payload_json = json.dumps(payload, sort_keys=True)
        current_hash = AuditService.calculate_hash(prev_hash, payload_json, created_at.isoformat())

        audit_entry = AuditLog(
            id=str(uuid4()),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            payload_json=payload_json,
            prev_hash=prev_hash,
            current_hash=current_hash,
            created_at=created_at,
        )

        db.add(audit_entry)
        await db.flush()
        return audit_entry

    @staticmethod
    async def verify_chain(db: AsyncSession) -> dict:
        result = await db.execute(
            select(AuditLog).order_by(AuditLog.sequence_number.asc())
        )
        records = result.scalars().all()

        if not records:
            return {
                "is_valid": True,
                "total_records_checked": 0,
                "corrupted_sequence_number": None,
                "message": "Audit chain is empty and intact.",
            }

        expected_prev_hash = GENESIS_HASH
        for i, rec in enumerate(records):
            # 1. Check prev_hash link
            if rec.prev_hash != expected_prev_hash:
                return {
                    "is_valid": False,
                    "total_records_checked": i,
                    "corrupted_sequence_number": rec.sequence_number,
                    "message": f"Broken hash chain link at record sequence {rec.sequence_number}.",
                }

            # 2. Check current_hash computation
            computed_hash = AuditService.calculate_hash(
                rec.prev_hash, rec.payload_json, rec.created_at.isoformat()
            )
            if computed_hash != rec.current_hash:
                return {
                    "is_valid": False,
                    "total_records_checked": i,
                    "corrupted_sequence_number": rec.sequence_number,
                    "message": f"Tampered data detected in record sequence {rec.sequence_number}.",
                }

            expected_prev_hash = rec.current_hash

        return {
            "is_valid": True,
            "total_records_checked": len(records),
            "corrupted_sequence_number": None,
            "message": f"All {len(records)} audit records in chain verified successfully.",
        }
