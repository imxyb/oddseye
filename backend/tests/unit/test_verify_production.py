from __future__ import annotations

import pytest

from app.tools.verify_production import (
    HttpProductionClient,
    ProductionVerificationError,
    verify_production,
)


class FakeProductionClient:
    def __init__(
        self,
        responses: dict[tuple[str, str], dict | list[dict]],
        text_responses: dict[tuple[str, str], str] | None = None,
    ):
        self.responses = responses
        self.text_responses = text_responses or {}
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
        response = self.responses[(method, path)]
        if isinstance(response, list):
            return response.pop(0)
        return response

    def request_text(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
    ) -> str:
        self.calls.append((method, path, token, None))
        return self.text_responses[(method, path)]


def _successful_responses() -> dict[tuple[str, str], dict | list[dict]]:
    return {
        ("GET", "/health"): {"status": "ok"},
        ("POST", "/auth/login"): {"access_token": "token-123"},
        ("GET", "/auth/me"): {"username": "admin", "role": "admin"},
        ("GET", "/radar/markets?limit=3"): {"items": [{"market_id": "market-1"}]},
        ("GET", "/radar/markets?category=crypto&sort=quality&limit=5"): {
            "items": [
                {"market_id": "quality-1", "market_quality_score": 91, "closes_at": "2026-07-03T00:00:00+00:00"},
                {"market_id": "quality-2", "market_quality_score": 80, "closes_at": "2026-07-04T00:00:00+00:00"},
            ],
        },
        ("GET", "/radar/markets?category=crypto&sort=volume&limit=5"): {
            "items": [
                {"market_id": "volume-1", "volume_usd_24h": 9000, "closes_at": "2026-07-03T00:00:00+00:00"},
                {"market_id": "volume-2", "volume_usd_24h": 5000, "closes_at": "2026-07-04T00:00:00+00:00"},
            ],
        },
        ("GET", "/radar/markets?category=crypto&sort=liquidity&limit=5"): {
            "items": [
                {"market_id": "liquidity-1", "liquidity_usd": 12000, "closes_at": "2026-07-03T00:00:00+00:00"},
                {"market_id": "liquidity-2", "liquidity_usd": 4000, "closes_at": "2026-07-04T00:00:00+00:00"},
            ],
        },
        ("GET", "/radar/markets?category=crypto&sort=closingSoon&limit=5"): {
            "items": [
                {"market_id": "closing-1", "closes_at": "2026-07-03T00:00:00+00:00"},
                {"market_id": "closing-2", "closes_at": "2026-07-04T00:00:00+00:00"},
            ],
        },
        ("GET", "/radar/markets?category=crypto&limit=3"): {
            "items": [{"market_id": "crypto-market"}],
        },
        ("GET", "/radar/markets?category=economics&limit=3"): {
            "items": [{"market_id": "macro-market"}],
        },
        (
            "GET",
            "/markets/market-1",
        ): {
            "market_id": "market-1",
            "outcomes": [{"index": 0, "bid": 0.48, "ask": 0.5, "spread": 0.02}],
            "liquidity_usd": 25000,
            "market_quality_score": 80,
            "quality": {
                "components": {
                    "liquidity": 75,
                    "spread": 100,
                    "resolution_clarity": 80,
                    "modelability": 90,
                    "time": 100,
                    "activity": 60,
                },
                "reason_codes": ["LIQUIDITY_OK", "SPREAD_OK"],
                "risk_flags": [],
                "passes_paper_gate": True,
            },
        },
        ("POST", "/paper/orders"): [
            {
                "order": {
                    "order_id": "manual-buy-order",
                    "market_id": "market-1",
                    "signal_id": None,
                    "status": "filled",
                },
                "fill": {"fill_id": "manual-buy-fill", "price": 0.50125, "snapshot_id": 10},
                "position": {"position_id": "manual-position", "quantity": 0.01, "status": "open"},
            },
            {
                "order": {
                    "order_id": "manual-sell-order",
                    "market_id": "market-1",
                    "signal_id": None,
                    "status": "filled",
                },
                "fill": {"fill_id": "manual-sell-fill", "price": 0.4788, "snapshot_id": 12},
                "position": {"position_id": "manual-position", "quantity": 0, "status": "closed"},
            },
        ],
        (
            "GET",
            "/markets/market-1/bars?range=7d&resolution=hour1",
        ): {"bars": [{"t": 1, "yes_bid": 0.48, "yes_ask": 0.5}]},
        ("GET", "/signals?limit=3"): {"items": [{"signal_id": "signal-1"}]},
        ("GET", "/signals?category=crypto&limit=20"): {
            "items": [
                {
                    "signal_id": "signal-crypto-threshold",
                    "market_id": "market-1",
                    "strategy_code": "crypto_threshold_v1",
                    "question": "Will BTC be above $80,000 on July 31, 2026?",
                    "category": "crypto",
                    "action": "BUY",
                    "side": "YES",
                    "executable_price": 0.5,
                }
            ],
        },
        ("GET", "/signals?action=BUY&limit=5"): {
            "items": [
                {
                    "signal_id": "signal-buy",
                    "market_id": "market-1",
                    "strategy_code": "crypto_threshold_v1",
                    "question": "Will BTC be above $80,000 on July 31, 2026?",
                    "category": "crypto",
                    "action": "BUY",
                    "side": "YES",
                    "executable_price": 0.5,
                }
            ],
        },
        ("POST", "/signals/signal-buy/paper-order"): {
            "order": {
                "order_id": "signal-order",
                "market_id": "market-1",
                "signal_id": "signal-buy",
                "status": "filled",
            },
            "fill": {"fill_id": "signal-fill", "price": 0.50125, "snapshot_id": 11},
            "position": {"position_id": "signal-position"},
        },
        ("GET", "/settings/usage"): {
            "today_requests": 3,
            "month_requests": 9,
            "jobs": {"signal_seconds": 300},
            "recent_jobs": [
                {
                    "job_name": "discover_events",
                    "started_at": "2026-07-02T00:00:00+00:00",
                    "finished_at": "2026-07-02T00:00:01+00:00",
                    "status": "success",
                    "records_processed": 3,
                    "codex_requests_used": 1,
                },
                {
                    "job_name": "sync_hot_markets",
                    "started_at": "2026-07-02T00:01:00+00:00",
                    "finished_at": "2026-07-02T00:01:01+00:00",
                    "status": "success",
                    "records_processed": 6,
                    "codex_requests_used": 2,
                },
                {
                    "job_name": "compute_quality",
                    "started_at": "2026-07-02T00:02:00+00:00",
                    "finished_at": "2026-07-02T00:02:01+00:00",
                    "status": "success",
                    "records_processed": 6,
                    "codex_requests_used": 0,
                },
            ],
        },
        ("GET", "/paper/performance"): {
            "cash": 1000,
            "equity": 1000,
            "position_value": 5,
            "realized_pnl": 0,
            "unrealized_pnl": 0.1,
            "win_rate": 0,
            "max_drawdown": 0,
            "total_trades": 0,
        },
        ("GET", "/paper/positions"): {
            "items": [
                {
                    "position_id": "position-1",
                    "market_id": "market-1",
                    "outcome_index": 0,
                    "quantity": 0.02,
                    "avg_price": 0.5,
                    "mark_price": 0.48,
                    "realized_pnl": 0,
                    "unrealized_pnl": -0.0004,
                    "status": "open",
                }
            ],
            "total": 1,
        },
    }


def _successful_text_responses() -> dict[tuple[str, str], str]:
    return {
        (
            "GET",
            "/paper/trades.csv",
        ): (
            "fill_id,order_id,signal_id,snapshot_id,market_id,strategy_code,price,created_at\n"
            "fill-1,order-1,signal-1,snapshot-1,market-1,crypto_threshold_v1,0.50125,2026-07-02T00:00:00Z\n"
            "fill-2,order-2,,snapshot-2,market-2,,0.45000,2026-07-02T00:01:00Z\n"
        ),
    }


def test_verify_production_checks_documented_endpoints() -> None:
    client = FakeProductionClient(_successful_responses(), _successful_text_responses())

    checks = verify_production(
        base_url="https://oddseye.fun/",
        username="admin",
        password="secret",
        client=client,
    )

    assert [check.name for check in checks] == [
        "health",
        "login",
        "auth_me",
        "radar",
        "radar_sort_quality",
        "radar_sort_volume",
        "radar_sort_liquidity",
        "radar_sort_closingSoon",
        "crypto_markets",
        "macro_markets",
        "market_detail",
        "market_quality_explanation",
        "paper_manual_order",
        "paper_manual_sell_order",
        "market_bars",
        "signals",
        "crypto_threshold_signal",
        "paper_signal_order",
        "usage",
        "scheduled_jobs",
        "paper_performance",
        "paper_positions",
        "paper_trade_traceability",
    ]
    assert all(check.ok for check in checks)
    assert client.calls == [
        ("GET", "/health", None, None),
        ("POST", "/auth/login", None, {"username": "admin", "password": "secret"}),
        ("GET", "/auth/me", "token-123", None),
        ("GET", "/radar/markets?limit=3", "token-123", None),
        ("GET", "/radar/markets?category=crypto&sort=quality&limit=5", "token-123", None),
        ("GET", "/radar/markets?category=crypto&sort=volume&limit=5", "token-123", None),
        ("GET", "/radar/markets?category=crypto&sort=liquidity&limit=5", "token-123", None),
        ("GET", "/radar/markets?category=crypto&sort=closingSoon&limit=5", "token-123", None),
        ("GET", "/radar/markets?category=crypto&limit=3", "token-123", None),
        ("GET", "/radar/markets?category=economics&limit=3", "token-123", None),
        ("GET", "/markets/market-1", "token-123", None),
        (
            "POST",
            "/paper/orders",
            "token-123",
            {
                "market_id": "market-1",
                "side": "BUY",
                "outcome_index": 0,
                "limit_price": "0.5",
                "quantity": "0.01",
            },
        ),
        (
            "POST",
            "/paper/orders",
            "token-123",
            {
                "market_id": "market-1",
                "side": "SELL",
                "outcome_index": 0,
                "limit_price": "0.48",
                "quantity": "0.01",
            },
        ),
        ("GET", "/markets/market-1/bars?range=7d&resolution=hour1", "token-123", None),
        ("GET", "/signals?limit=3", "token-123", None),
        ("GET", "/signals?category=crypto&limit=20", "token-123", None),
        ("GET", "/signals?action=BUY&limit=5", "token-123", None),
        (
            "POST",
            "/signals/signal-buy/paper-order",
            "token-123",
            {"notional": "0.01", "limit_price": "0.5"},
        ),
        ("GET", "/settings/usage", "token-123", None),
        ("GET", "/paper/performance", "token-123", None),
        ("GET", "/paper/positions", "token-123", None),
        ("GET", "/paper/trades.csv", "token-123", None),
    ]


def test_verify_production_rejects_empty_live_signal_response() -> None:
    responses = _successful_responses()
    responses[("GET", "/signals?limit=3")] = {"items": []}
    client = FakeProductionClient(responses, _successful_text_responses())

    with pytest.raises(ProductionVerificationError, match="signals"):
        verify_production(
            base_url="https://oddseye.fun",
            username="admin",
            password="secret",
            client=client,
        )


def test_verify_production_rejects_login_token_without_config_user_identity() -> None:
    responses = _successful_responses()
    responses[("GET", "/auth/me")] = {"username": "other", "role": "admin"}
    client = FakeProductionClient(responses, _successful_text_responses())

    with pytest.raises(ProductionVerificationError, match="auth_me"):
        verify_production(
            base_url="https://oddseye.fun",
            username="admin",
            password="secret",
            client=client,
        )


def test_verify_production_rejects_unsorted_radar_dimension() -> None:
    responses = _successful_responses()
    responses[("GET", "/radar/markets?category=crypto&sort=volume&limit=5")] = {
        "items": [
            {"market_id": "volume-1", "volume_usd_24h": 1000},
            {"market_id": "volume-2", "volume_usd_24h": 5000},
        ],
    }
    client = FakeProductionClient(responses, _successful_text_responses())

    with pytest.raises(ProductionVerificationError, match="radar_sort_volume"):
        verify_production(
            base_url="https://oddseye.fun",
            username="admin",
            password="secret",
            client=client,
        )


def test_verify_production_rejects_non_conservative_manual_buy_fill() -> None:
    responses = _successful_responses()
    responses[("POST", "/paper/orders")] = [{
        "order": {"order_id": "manual-order", "market_id": "market-1", "status": "filled"},
        "fill": {"fill_id": "manual-fill", "price": 0.49, "snapshot_id": 10},
        "position": {"position_id": "manual-position"},
    }]
    client = FakeProductionClient(responses, _successful_text_responses())

    with pytest.raises(ProductionVerificationError, match="paper_manual_order"):
        verify_production(
            base_url="https://oddseye.fun",
            username="admin",
            password="secret",
            client=client,
        )


def test_verify_production_rejects_non_conservative_manual_sell_fill() -> None:
    responses = _successful_responses()
    responses[("POST", "/paper/orders")] = [
        {
            "order": {"order_id": "manual-buy-order", "market_id": "market-1", "status": "filled"},
            "fill": {"fill_id": "manual-buy-fill", "price": 0.50125, "snapshot_id": 10},
            "position": {"position_id": "manual-position"},
        },
        {
            "order": {"order_id": "manual-sell-order", "market_id": "market-1", "status": "filled"},
            "fill": {"fill_id": "manual-sell-fill", "price": 0.481, "snapshot_id": 12},
            "position": {"position_id": "manual-position"},
        },
    ]
    client = FakeProductionClient(responses, _successful_text_responses())

    with pytest.raises(ProductionVerificationError, match="paper_manual_sell_order"):
        verify_production(
            base_url="https://oddseye.fun",
            username="admin",
            password="secret",
            client=client,
        )


def test_verify_production_rejects_missing_quality_explanation() -> None:
    responses = _successful_responses()
    responses[("GET", "/markets/market-1")] = {
        "market_id": "market-1",
        "outcomes": [{"index": 0, "bid": 0.48, "ask": 0.5, "spread": 0.02}],
        "liquidity_usd": 25000,
        "market_quality_score": 80,
    }
    client = FakeProductionClient(responses, _successful_text_responses())

    with pytest.raises(ProductionVerificationError, match="market_quality_explanation"):
        verify_production(
            base_url="https://oddseye.fun",
            username="admin",
            password="secret",
            client=client,
        )


def test_verify_production_rejects_incomplete_quality_components() -> None:
    responses = _successful_responses()
    responses[("GET", "/markets/market-1")]["quality"]["components"] = {"liquidity": 75}
    client = FakeProductionClient(responses, _successful_text_responses())

    with pytest.raises(ProductionVerificationError, match="market_quality_explanation"):
        verify_production(
            base_url="https://oddseye.fun",
            username="admin",
            password="secret",
            client=client,
        )


def test_verify_production_rejects_unfilled_signal_paper_order() -> None:
    responses = _successful_responses()
    responses[("POST", "/signals/signal-buy/paper-order")] = {
        "order": {
            "order_id": "signal-order",
            "market_id": "market-1",
            "signal_id": "signal-buy",
            "status": "open",
        },
        "fill": None,
        "position": None,
    }
    client = FakeProductionClient(responses, _successful_text_responses())

    with pytest.raises(ProductionVerificationError, match="paper_signal_order"):
        verify_production(
            base_url="https://oddseye.fun",
            username="admin",
            password="secret",
            client=client,
        )


def test_verify_production_rejects_missing_crypto_threshold_signal() -> None:
    responses = _successful_responses()
    responses[("GET", "/signals?category=crypto&limit=20")] = {
        "items": [
            {
                "signal_id": "signal-other",
                "market_id": "market-2",
                "strategy_code": "macro_calendar_v1",
                "question": "Will the next CPI print be above consensus?",
                "category": "economics",
                "action": "OBSERVE",
            }
        ],
    }
    client = FakeProductionClient(responses, _successful_text_responses())

    with pytest.raises(ProductionVerificationError, match="crypto_threshold_signal"):
        verify_production(
            base_url="https://oddseye.fun",
            username="admin",
            password="secret",
            client=client,
        )


def test_verify_production_skips_invalid_crypto_threshold_candidates() -> None:
    responses = _successful_responses()
    responses[("GET", "/signals?category=crypto&limit=20")] = {
        "items": [
            {
                "signal_id": "signal-parser-failed",
                "market_id": "market-2",
                "strategy_code": "crypto_threshold_v1",
                "question": "BTC price up in next 15 mins?",
                "category": "crypto",
                "action": "IGNORE",
            },
            {
                "signal_id": "signal-valid-threshold",
                "market_id": "market-1",
                "strategy_code": "crypto_threshold_v1",
                "question": "Will the price of Bitcoin be above $62,000 on July 1?",
                "category": "crypto",
                "action": "OBSERVE",
            },
        ],
    }
    client = FakeProductionClient(responses, _successful_text_responses())

    checks = verify_production(
        base_url="https://oddseye.fun",
        username="admin",
        password="secret",
        client=client,
    )

    assert any(check.name == "crypto_threshold_signal" for check in checks)


def test_verify_production_rejects_missing_ingest_job_run() -> None:
    responses = _successful_responses()
    responses[("GET", "/settings/usage")]["recent_jobs"] = [
        {
            "job_name": "discover_events",
            "started_at": "2026-07-02T00:00:00+00:00",
            "finished_at": "2026-07-02T00:00:01+00:00",
            "status": "success",
            "records_processed": 3,
            "codex_requests_used": 1,
        },
        {
            "job_name": "compute_quality",
            "started_at": "2026-07-02T00:02:00+00:00",
            "finished_at": "2026-07-02T00:02:01+00:00",
            "status": "success",
            "records_processed": 6,
            "codex_requests_used": 0,
        },
    ]
    client = FakeProductionClient(responses, _successful_text_responses())

    with pytest.raises(ProductionVerificationError, match="scheduled_jobs"):
        verify_production(
            base_url="https://oddseye.fun",
            username="admin",
            password="secret",
            client=client,
        )


def test_verify_production_rejects_performance_without_pnl_fields() -> None:
    responses = _successful_responses()
    responses[("GET", "/paper/performance")] = {
        "cash": 1000,
        "equity": 1000,
        "win_rate": 0,
        "max_drawdown": 0,
        "total_trades": 0,
    }
    client = FakeProductionClient(responses, _successful_text_responses())

    with pytest.raises(ProductionVerificationError, match="paper_performance"):
        verify_production(
            base_url="https://oddseye.fun",
            username="admin",
            password="secret",
            client=client,
        )


def test_verify_production_rejects_missing_paper_positions() -> None:
    responses = _successful_responses()
    responses[("GET", "/paper/positions")] = {"items": [], "total": 0}
    client = FakeProductionClient(responses, _successful_text_responses())

    with pytest.raises(ProductionVerificationError, match="paper_positions"):
        verify_production(
            base_url="https://oddseye.fun",
            username="admin",
            password="secret",
            client=client,
        )


def test_verify_production_rejects_untraceable_signal_trade() -> None:
    client = FakeProductionClient(
        _successful_responses(),
        {
            (
                "GET",
                "/paper/trades.csv",
            ): (
                "fill_id,order_id,signal_id,snapshot_id,market_id,strategy_code,price,created_at\n"
                "fill-1,order-1,,snapshot-1,market-1,crypto_threshold_v1,0.50125,2026-07-02T00:00:00Z\n"
            ),
        },
    )

    with pytest.raises(ProductionVerificationError, match="paper_trade_traceability"):
        verify_production(
            base_url="https://oddseye.fun",
            username="admin",
            password="secret",
            client=client,
        )


def test_verify_production_rejects_trade_without_snapshot_or_price() -> None:
    client = FakeProductionClient(
        _successful_responses(),
        {
            (
                "GET",
                "/paper/trades.csv",
            ): (
                "fill_id,order_id,signal_id,snapshot_id,market_id,strategy_code,price,created_at\n"
                "fill-1,order-1,signal-1,,market-1,crypto_threshold_v1,,2026-07-02T00:00:00Z\n"
            ),
        },
    )

    with pytest.raises(ProductionVerificationError, match="paper_trade_traceability"):
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
