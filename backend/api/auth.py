"""Auth router: POST /api/v1/auth/login"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from backend.auth import create_access_token, verify_password
from backend.db import _db_session_dependency
from backend.models import User
from backend.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest,
                session=Depends(_db_session_dependency)) -> TokenResponse:
    result = await session.execute(
        select(User).where(User.username == body.username, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token, expires_in = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(access_token=token, expires_in=expires_in)
