# backend/app/models/audit.py
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text
from backend.app.config.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, index=True)
    sequence_number = Column(Integer, unique=True, index=True, autoincrement=True)
    action = Column(String, nullable=False) # e.g. "SCAN_CREATED", "GRADE_CALCULATED", "DISPUTE_FILED", "DISPUTE_RESOLVED"
    entity_type = Column(String, nullable=False) # e.g. "Scan", "GradingResult", "Dispute"
    entity_id = Column(String, nullable=False)
    actor_id = Column(String, nullable=False)
    payload_json = Column(Text, nullable=False)
    prev_hash = Column(String, nullable=False) # SHA-256 hash of previous audit record
    current_hash = Column(String, nullable=False) # SHA-256(prev_hash + payload_json + timestamp)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
