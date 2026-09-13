# backend/app/schemas/auth.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from backend.app.models.user import UserRoleEnum

class SendOTPRequest(BaseModel):
    phone: str = Field(..., example="+91 98230 11223")

class SendOTPResponse(BaseModel):
    status: str = "success"
    message: str = "OTP sent successfully"
    expires_in_seconds: int = 300

class VerifyOTPRequest(BaseModel):
    phone: str = Field(..., example="+91 98230 11223")
    otp: str = Field(..., example="123456")
    role: UserRoleEnum = Field(default=UserRoleEnum.FARMER)
    name: Optional[str] = "Farmer Name"
    procurement_center_id: Optional[str] = "APMC-LASALGAON-01"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    name: str
    role: UserRoleEnum
    procurement_center_id: str

class UserResponse(BaseModel):
    id: str
    phone: str
    name: str
    role: UserRoleEnum
    procurement_center_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
