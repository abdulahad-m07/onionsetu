# backend/app/models/scan.py
import enum
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from backend.app.config.database import Base

class SyncStatusEnum(str, enum.Enum):
    PENDING = "pendingOffline"
    UPLOADING = "uploading"
    SYNCED = "synced"
    FAILED = "failed"

class SamplingAngleEnum(str, enum.Enum):
    TOP_VIEW = "topView"
    SIDE_VIEW = "sideView"
    SPREAD_VIEW = "spreadView"

class DefectTypeEnum(str, enum.Enum):
    GRADE_A = "gradeA"
    DAMAGED = "damaged"
    ROTTEN = "rotten"
    SPROUTED = "sprouted"
    UNDERSIZED = "undersized"
    UNKNOWN = "unknown"

class ConfidenceGateStatusEnum(str, enum.Enum):
    HIGH_CONFIDENCE = "highConfidence"
    BORDERLINE_REVIEW = "borderlineReview"

class Scan(Base):
    __tablename__ = "scans"

    id = Column(String, primary_key=True, index=True)
    lot_number = Column(String, index=True, nullable=False)
    farmer_name = Column(String, nullable=False)
    farmer_phone = Column(String, index=True, nullable=False)
    procurement_center_id = Column(String, index=True, nullable=False)
    grader_id = Column(String, ForeignKey("users.id"), nullable=False)
    sync_status = Column(SQLEnum(SyncStatusEnum), default=SyncStatusEnum.SYNCED, nullable=False)
    report_url = Column(String, nullable=True)
    audit_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    grader = relationship("User", back_populates="scans", foreign_keys=[grader_id])
    images = relationship("CapturedImage", back_populates="scan", cascade="all, delete-orphan")
    detections = relationship("Detection", back_populates="scan", cascade="all, delete-orphan")
    result = relationship("GradingResult", back_populates="scan", uselist=False, cascade="all, delete-orphan")
    disputes = relationship("Dispute", back_populates="scan", cascade="all, delete-orphan")

class CapturedImage(Base):
    __tablename__ = "captured_images"

    id = Column(String, primary_key=True, index=True)
    scan_id = Column(String, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    local_path = Column(String, nullable=False)
    remote_storage_url = Column(String, nullable=True)
    angle = Column(SQLEnum(SamplingAngleEnum), default=SamplingAngleEnum.TOP_VIEW, nullable=False)
    sharpness_score = Column(Float, nullable=True)
    brightness_score = Column(Float, nullable=True)
    quality_passed = Column(Boolean, default=True, nullable=False)
    captured_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    scan = relationship("Scan", back_populates="images")

class Detection(Base):
    __tablename__ = "detections"

    id = Column(String, primary_key=True, index=True)
    scan_id = Column(String, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    defect_type = Column(SQLEnum(DefectTypeEnum), nullable=False)
    confidence = Column(Float, nullable=False)
    estimated_diameter_mm = Column(Float, nullable=True)
    view_angle = Column(String, nullable=True)

    scan = relationship("Scan", back_populates="detections")

class GradingResult(Base):
    __tablename__ = "grading_results"

    id = Column(String, primary_key=True, index=True)
    scan_id = Column(String, ForeignKey("scans.id", ondelete="CASCADE"), unique=True, nullable=False)
    grade_a_percentage = Column(Float, nullable=False)
    urs_percentage = Column(Float, nullable=False)
    average_ai_confidence = Column(Float, nullable=False)
    confidence_status = Column(SQLEnum(ConfidenceGateStatusEnum), default=ConfidenceGateStatusEnum.HIGH_CONFIDENCE, nullable=False)
    policy_version = Column(String, default="v1.0.0", nullable=False)
    total_onions_count = Column(Integer, nullable=False)
    grade_a_count = Column(Integer, nullable=False)
    damaged_count = Column(Integer, nullable=False)
    rotten_count = Column(Integer, nullable=False)
    sprouted_count = Column(Integer, nullable=False)
    undersized_count = Column(Integer, nullable=False)
    avg_size_mm = Column(Float, nullable=True)
    audit_hash = Column(String, nullable=True)
    calculated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    scan = relationship("Scan", back_populates="result")
