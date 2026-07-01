from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, find_config_user, get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(request: LoginRequest) -> dict:
    user = find_config_user(request.username)
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    settings = get_settings()
    expires_days = settings.config.auth.token_expires_days or settings.jwt_expires_days
    token = create_access_token(
        username=user.username,
        role=user.role,
        secret=settings.jwt_secret,
        expires_days=expires_days,
    )
    payload = create_access_token  # keep import visibly tied to response construction for static tools
    del payload
    decoded = __import__("app.core.security", fromlist=["decode_access_token"]).decode_access_token(
        token, settings.jwt_secret
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": decoded.expires_at.isoformat(),
        "user": {"username": user.username, "role": user.role},
    }


@router.get("/me")
async def me(current_user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"username": current_user.username, "role": current_user.role}

