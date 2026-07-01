from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import create_app


@pytest.mark.asyncio
async def test_configured_ip_allowlist_rejects_unlisted_clients(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        """
auth:
  ip_allowlist:
    - 203.0.113.5
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    get_settings.cache_clear()

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        rejected = await client.get("/health", headers={"X-Forwarded-For": "198.51.100.9"})
        allowed = await client.get("/health", headers={"X-Forwarded-For": "203.0.113.5"})

    assert rejected.status_code == 403
    assert rejected.json()["detail"] == "IP not allowed"
    assert allowed.status_code == 200
    get_settings.cache_clear()
