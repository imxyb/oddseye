from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

ALGORITHM = "HS256"


@dataclass(frozen=True)
class TokenPayload:
    username: str
    role: str
    expires_at: datetime


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(username: str, role: str, secret: str, expires_days: int) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=expires_days)
    payload: dict[str, Any] = {
        "sub": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise ValueError("invalid token") from exc
    username = payload.get("sub")
    role = payload.get("role")
    expires_at = payload.get("exp")
    if not isinstance(username, str) or not isinstance(role, str) or expires_at is None:
        raise ValueError("invalid token payload")
    return TokenPayload(
        username=username,
        role=role,
        expires_at=datetime.fromtimestamp(float(expires_at), tz=UTC),
    )

