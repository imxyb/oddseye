from __future__ import annotations

import pytest

from app.core.config import get_settings


def test_prod_rejects_short_jwt_secret(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("JWT_SECRET", "short")
    monkeypatch.setenv("APP_CONFIG_PATH", str(tmp_path / "missing.yaml"))
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="JWT_SECRET"):
        get_settings()

    get_settings.cache_clear()
