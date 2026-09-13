# backend/app/models/user.py
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from backend.app.config.database import Base

class UserRoleEnum(str, enum.Enum):
    FARMER = "farmer"
    GRADER = "grader"
    ADMIN = "admin"

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    role = Column(SQLEnum(UserRoleEnum), default=UserRoleEnum.FARMER, nullable=False)
    procurement_center_id = Column(String, default="APMC-LASALGAON-01")
    hashed_password = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    scans = relationship("Scan", back_populates="grader", foreign_keys="Scan.grader_id")
    disputes = relationship("Dispute", back_populates="filed_by", foreign_keys="Dispute.filed_by_user_id")
