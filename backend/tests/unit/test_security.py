from datetime import UTC, datetime

import pytest

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_verification_round_trip() -> None:
    hashed = hash_password("correct horse battery staple")

    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_access_token_contains_subject_role_and_expiration() -> None:
    token = create_access_token(username="biaoge", role="admin", secret="x" * 32, expires_days=7)
    payload = decode_access_token(token, secret="x" * 32)

    assert payload.username == "biaoge"
    assert payload.role == "admin"
    assert payload.expires_at > datetime.now(UTC)


def test_invalid_access_token_is_rejected() -> None:
    with pytest.raises(ValueError):
        decode_access_token("not-a-jwt", secret="x" * 32)

