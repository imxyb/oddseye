from __future__ import annotations

import pytest

from app.tools.verify_production import (
    HttpProductionClient,
    ProductionVerificationError,
    verify_production,
)


class FakeProductionClient:
    def __init__(self, responses: dict[tuple[str, str], dict]):
        self.responses = responses
        self.calls: list[tuple[str, str, str | None, dict | None]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json_body: dict | None = None,
    ) -> dict:
        self.calls.append((method, path, token, json_body))
        return self.responses[(method, path)]


def _successful_responses() -> dict[tuple[str, str], dict]:
    return {
        ("GET", "/health"): {"status": "ok"},
        ("POST", "/auth/login"): {"access_token": "token-123"},
        ("GET", "/radar/markets?limit=3"): {"items": [{"market_id": "market-1"}]},
        ("GET", "/signals?limit=3"): {"items": [{"signal_id": "signal-1"}]},
        ("GET", "/settings/usage"): {"today_requests": 3, "jobs": {"signal_seconds": 300}},
        ("GET", "/paper/performance"): {
            "cash": 1000,
            "equity": 1000,
            "win_rate": 0,
            "max_drawdown": 0,
            "total_trades": 0,
        },
    }


def test_verify_production_checks_documented_endpoints() -> None:
    client = FakeProductionClient(_successful_responses())

    checks = verify_production(
        base_url="https://oddseye.fun/",
        username="admin",
        password="secret",
        client=client,
    )

    assert [check.name for check in checks] == [
        "health",
        "login",
        "radar",
        "signals",
        "usage",
        "paper_performance",
    ]
    assert all(check.ok for check in checks)
    assert client.calls == [
        ("GET", "/health", None, None),
        ("POST", "/auth/login", None, {"username": "admin", "password": "secret"}),
        ("GET", "/radar/markets?limit=3", "token-123", None),
        ("GET", "/signals?limit=3", "token-123", None),
        ("GET", "/settings/usage", "token-123", None),
        ("GET", "/paper/performance", "token-123", None),
    ]


def test_verify_production_rejects_empty_live_signal_response() -> None:
    responses = _successful_responses()
    responses[("GET", "/signals?limit=3")] = {"items": []}
    client = FakeProductionClient(responses)

    with pytest.raises(ProductionVerificationError, match="signals"):
        verify_production(
            base_url="https://oddseye.fun",
            username="admin",
            password="secret",
            client=client,
        )


def test_http_production_client_ignores_shell_proxy_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    request_kwargs: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"status": "ok"}

    def fake_request(method: str, url: str, **kwargs) -> FakeResponse:
        request_kwargs.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.tools.verify_production.httpx.request", fake_request)

    client = HttpProductionClient("https://oddseye.fun")

    assert client.request("GET", "/health") == {"status": "ok"}
    assert request_kwargs["trust_env"] is False
