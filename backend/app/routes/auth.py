# backend/app/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import uuid4
from backend.app.config.database import get_db
from backend.app.models.user import User, UserRoleEnum
from backend.app.schemas.auth import SendOTPRequest, SendOTPResponse, VerifyOTPRequest, TokenResponse, UserResponse
from backend.app.services.auth_service import AuthService, get_current_user
from backend.app.config.settings import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/send-otp", response_model=SendOTPResponse)
async def send_otp(req: SendOTPRequest):
    AuthService.generate_otp(req.phone)
    return SendOTPResponse(status="success", message=f"OTP sent to {req.phone}")

@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(req: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    if not AuthService.verify_otp(req.phone, req.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code."
        )

    # Find or create user
    result = await db.execute(select(User).where(User.phone == req.phone))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=str(uuid4()),
            phone=req.phone,
            name=req.name or "Onion Farmer",
            role=req.role,
            procurement_center_id=req.procurement_center_id or "APMC-LASALGAON-01",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = AuthService.create_access_token(
        user_id=user.id,
        role=user.role,
        extra={"phone": user.phone, "name": user.name, "center": user.procurement_center_id},
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        name=user.name,
        role=user.role,
        procurement_center_id=user.procurement_center_id,
    )

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
