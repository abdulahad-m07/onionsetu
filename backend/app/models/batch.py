# backend/app/models/batch.py
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.config.database import Base

# New table (not an ALTER): Base.metadata.create_all() creates it on fresh
# and existing databases without touching scan/history/dispute/audit data.
# SQLite + PostgreSQL compatible column types only.
class BatchAssessment(Base):
    __tablename__ = "batch_assessments"

    id = Column(String, primary_key=True, index=True)
    scan_id = Column(String, ForeignKey("scans.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String, default="completed", nullable=False)
    final_grade = Column(String, nullable=False)  # A | B | C | Reject
    assessment_confidence = Column(Float, nullable=False)
    sample_size = Column(Integer, nullable=False)
    sample_size_estimated = Column(Boolean, default=True, nullable=False)
    images_analyzed = Column(Integer, nullable=False)
    review_required = Column(Boolean, default=False, nullable=False)
    review_reasons_json = Column(Text, nullable=True)
    policy_version = Column(String, nullable=False)
    # URS% = (provider-estimated URS onions / grader-declared batch size) x
    # 100, rounded to URS_PERCENT_PRECISION. Null when URS evidence was
    # unusable/unknown (policy then used the configured fallback + review).
    urs_percent = Column(Float, nullable=True)
    # Grader-declared physical batch size (100-200), preserved EXACTLY as
    # entered: the ONLY URS% denominator. Never derived from detections.
    assessed_onions_declared = Column(Integer, nullable=True)
    roboflow_model = Column(String, nullable=False)
    # Provider-neutral assessment model id (previously `gemini_model`;
    # renamed via migration in database.init_db — see _migrate_batch_model_column).
    assessment_model = Column(String, nullable=False)
    observations_json = Column(Text, nullable=True)
    issues_json = Column(Text, nullable=True)
    evidence_json = Column(Text, nullable=True)
    calculated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    scan = relationship("Scan", backref="batch_assessments")
