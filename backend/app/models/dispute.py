# backend/app/models/dispute.py
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from backend.app.config.database import Base

class DisputeStatusEnum(str, enum.Enum):
    PENDING_REVIEW = "pendingReview"
    IN_REVIEW = "inReview"
    UPHELD = "upheld"
    REJECTED = "rejected"

class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(String, primary_key=True, index=True)
    scan_id = Column(String, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    filed_by_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(SQLEnum(DisputeStatusEnum), default=DisputeStatusEnum.PENDING_REVIEW, nullable=False)
    reviewer_notes = Column(Text, nullable=True)
    reviewer_id = Column(String, ForeignKey("users.id"), nullable=True)
    revised_grade_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    scan = relationship("Scan", back_populates="disputes")
    filed_by = relationship("User", foreign_keys=[filed_by_user_id], back_populates="disputes")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
