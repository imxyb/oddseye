from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any, Protocol
from urllib.parse import quote

import httpx


class ProductionVerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class VerificationCheck:
    name: str
    ok: bool
    detail: str


VERIFY_PAPER_QUANTITY = Decimal("0.01")
VERIFY_PAPER_NOTIONAL = Decimal("0.01")
QUALITY_COMPONENT_NAMES = (
    "liquidity",
    "spread",
    "resolution_clarity",
    "modelability",
    "time",
    "activity",
)
SYNC_MARKET_JOB_NAMES = {"sync_hot_markets", "sync_warm_markets", "sync_cold_markets"}
CRYPTO_THRESHOLD_ASSETS = {"BTC", "BITCOIN", "ETH", "ETHEREUM", "SOL", "SOLANA"}


class ProductionClient(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json_body: dict | None = None,
    ) -> dict[str, Any]:
        ...

    def request_text(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
    ) -> str:
        ...

    def response_status(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
    ) -> int:
        ...


class HttpProductionClient:
    def __init__(self, base_url: str, timeout_seconds: int = 20):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json_body: dict | None = None,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                json=json_body,
                timeout=self.timeout_seconds,
                trust_env=False,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise ProductionVerificationError(f"{method} {path} failed: {exc}") from exc
        except ValueError as exc:
            raise ProductionVerificationError(f"{method} {path} returned non-JSON response") from exc
        if not isinstance(payload, dict):
            raise ProductionVerificationError(f"{method} {path} returned unexpected payload")
        return payload

    def request_text(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
    ) -> str:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=self.timeout_seconds,
                trust_env=False,
            )
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as exc:
            raise ProductionVerificationError(f"{method} {path} failed: {exc}") from exc

    def response_status(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
    ) -> int:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=self.timeout_seconds,
                trust_env=False,
            )
            return response.status_code
        except httpx.HTTPError as exc:
            raise ProductionVerificationError(f"{method} {path} failed: {exc}") from exc


def verify_production(
    *,
    base_url: str,
    username: str,
    password: str,
    client: ProductionClient | None = None,
) -> list[VerificationCheck]:
    production_client = client or HttpProductionClient(base_url)
    checks: list[VerificationCheck] = []

    health = production_client.request("GET", "/health")
    _require(health.get("status") == "ok", "health", "expected status=ok")
    checks.append(VerificationCheck("health", True, "status=ok"))

    login = production_client.request(
        "POST",
        "/auth/login",
        json_body={"username": username, "password": password},
    )
    token = login.get("access_token")
    _require(isinstance(token, str) and token, "login", "missing access_token")
    checks.append(VerificationCheck("login", True, "token issued"))

    current_user = production_client.request("GET", "/auth/me", token=token)
    _require_authenticated_user(current_user, expected_username=username)
    checks.append(VerificationCheck("auth_me", True, f"{username} token resolved to configured user"))

    _require_authenticated_endpoints(production_client)
    checks.append(VerificationCheck("auth_required", True, "protected endpoints reject missing bearer token"))

    radar = production_client.request("GET", "/radar/markets?limit=3", token=token)
    radar_count = _require_items(radar, "radar")
    checks.append(VerificationCheck("radar", True, f"{radar_count} markets returned"))

    _require_freshness(radar, "radar_freshness")
    checks.append(VerificationCheck("radar_freshness", True, "freshness and usage hint returned"))

    watchlist = production_client.request("GET", "/radar/markets?category=watchlist&limit=5", token=token)
    watchlist_count = _require_items(watchlist, "watchlist_markets")
    checks.append(VerificationCheck("watchlist_markets", True, f"{watchlist_count} watchlist markets returned"))

    for sort in ("quality", "volume", "liquidity", "closingSoon"):
        sort_payload = production_client.request(
            "GET",
            f"/radar/markets?category=crypto&sort={sort}&limit=5",
            token=token,
        )
        sorted_count = _require_radar_sort(sort_payload, sort)
        direction = "ascending" if sort == "closingSoon" else "descending"
        checks.append(
            VerificationCheck(
                f"radar_sort_{sort}",
                True,
                f"{sorted_count} crypto markets returned in {direction} order",
            )
        )

    crypto_markets = production_client.request(
        "GET",
        "/radar/markets?category=crypto&limit=3",
        token=token,
    )
    crypto_count = _require_items(crypto_markets, "crypto_markets")
    checks.append(VerificationCheck("crypto_markets", True, f"{crypto_count} markets returned"))

    macro_markets = production_client.request(
        "GET",
        "/radar/markets?category=economics&limit=3",
        token=token,
    )
    macro_count = _require_items(macro_markets, "macro_markets")
    checks.append(VerificationCheck("macro_markets", True, f"{macro_count} markets returned"))

    first_market = _first_market_id(radar)
    encoded_market_id = quote(first_market, safe="")
    detail = production_client.request("GET", f"/markets/{encoded_market_id}", token=token)
    _require_market_detail(detail)
    checks.append(VerificationCheck("market_detail", True, "quote and liquidity returned"))

    _require_freshness(detail, "market_detail_freshness")
    checks.append(VerificationCheck("market_detail_freshness", True, "freshness and usage hint returned"))

    _require_quality_explanation(detail)
    checks.append(
        VerificationCheck(
            "market_quality_explanation",
            True,
            "score components, reasons, risk flags, and paper gate returned",
        )
    )

    refresh = production_client.request("POST", f"/markets/{encoded_market_id}/refresh", token=token)
    refresh_count = _require_manual_refresh(refresh, first_market)
    checks.append(
        VerificationCheck(
            "market_manual_refresh",
            True,
            f"manual refresh processed {refresh_count} market records",
        )
    )

    manual_outcome_index, manual_bid, manual_ask = _first_tradable_quote(detail)
    manual_order = production_client.request(
        "POST",
        "/paper/orders",
        token=token,
        json_body={
            "market_id": first_market,
            "side": "BUY",
            "outcome_index": manual_outcome_index,
            "limit_price": str(manual_ask),
            "quantity": str(VERIFY_PAPER_QUANTITY),
        },
    )
    _require_paper_buy_fill(
        manual_order,
        name="paper_manual_order",
        reference_price=manual_ask,
        expected_signal_id=None,
    )
    checks.append(
        VerificationCheck(
            "paper_manual_order",
            True,
            "manual BUY order filled at or above displayed ask",
        )
    )

    manual_sell_order = production_client.request(
        "POST",
        "/paper/orders",
        token=token,
        json_body={
            "market_id": first_market,
            "side": "SELL",
            "outcome_index": manual_outcome_index,
            "limit_price": str(manual_bid),
            "quantity": str(VERIFY_PAPER_QUANTITY),
        },
    )
    _require_paper_sell_fill(
        manual_sell_order,
        name="paper_manual_sell_order",
        reference_price=manual_bid,
        expected_signal_id=None,
    )
    checks.append(
        VerificationCheck(
            "paper_manual_sell_order",
            True,
            "manual SELL order filled at or below displayed bid",
        )
    )

    bars = production_client.request(
        "GET",
        f"/markets/{encoded_market_id}/bars?range=7d&resolution=hour1",
        token=token,
    )
    bar_count = _require_bars(bars)
    checks.append(VerificationCheck("market_bars", True, f"{bar_count} bars returned"))

    _require_freshness(bars, "market_bars_freshness")
    checks.append(VerificationCheck("market_bars_freshness", True, "freshness and usage hint returned"))

    signals = production_client.request("GET", "/signals?limit=3", token=token)
    signal_count = _require_items(signals, "signals")
    checks.append(VerificationCheck("signals", True, f"{signal_count} signals returned"))

    crypto_signals = production_client.request("GET", "/signals?category=crypto&limit=20", token=token)
    crypto_signal = _require_crypto_threshold_signal(crypto_signals)
    checks.append(
        VerificationCheck(
            "crypto_threshold_signal",
            True,
            f"{crypto_signal['strategy_code']} signal returned for crypto threshold market",
        )
    )

    buy_signals = production_client.request("GET", "/signals?action=BUY&limit=5", token=token)
    _require_signal_action(buy_signals, "BUY", name="signal_action_BUY")
    checks.append(VerificationCheck("signal_action_BUY", True, "BUY signal action returned"))

    observe_signals = production_client.request("GET", "/signals?action=OBSERVE&limit=5", token=token)
    _require_signal_action(observe_signals, "OBSERVE", name="signal_action_OBSERVE")
    checks.append(VerificationCheck("signal_action_OBSERVE", True, "OBSERVE signal action returned"))

    ignore_signals = production_client.request("GET", "/signals?action=IGNORE&limit=5", token=token)
    _require_signal_action(ignore_signals, "IGNORE", name="signal_action_IGNORE")
    checks.append(VerificationCheck("signal_action_IGNORE", True, "IGNORE signal action returned"))

    buy_signal = _first_orderable_buy_signal(buy_signals)
    signal_id = buy_signal["signal_id"]
    signal_limit_price = _decimal_payload_value(
        buy_signal.get("executable_price"),
        "paper_signal_order",
        "signal executable_price",
    )
    signal_order = production_client.request(
        "POST",
        f"/signals/{quote(signal_id, safe='')}/paper-order",
        token=token,
        json_body={
            "notional": str(VERIFY_PAPER_NOTIONAL),
            "limit_price": str(signal_limit_price),
        },
    )
    _require_paper_buy_fill(
        signal_order,
        name="paper_signal_order",
        reference_price=signal_limit_price,
        expected_signal_id=signal_id,
    )
    checks.append(
        VerificationCheck(
            "paper_signal_order",
            True,
            "BUY signal paper order filled at or above executable price",
        )
    )

    signal_order_payload = signal_order.get("order")
    _require(isinstance(signal_order_payload, dict), "paper_signal_sell_order", "missing signal order")
    signal_market_id = signal_order_payload.get("market_id")
    _require(
        isinstance(signal_market_id, str) and signal_market_id,
        "paper_signal_sell_order",
        "signal order missing market_id",
    )
    signal_outcome_index = signal_order_payload.get("outcome_index")
    _require(
        isinstance(signal_outcome_index, int) and not isinstance(signal_outcome_index, bool),
        "paper_signal_sell_order",
        "signal order missing outcome_index",
    )
    signal_quantity = _decimal_payload_value(
        signal_order_payload.get("quantity"),
        "paper_signal_sell_order",
        "signal order quantity",
    )
    signal_detail = production_client.request(
        "GET",
        f"/markets/{quote(signal_market_id, safe='')}",
        token=token,
    )
    signal_bid, _signal_ask = _tradable_quote_for_outcome(
        signal_detail,
        signal_outcome_index,
        name="paper_signal_sell_order",
    )
    signal_sell_order = production_client.request(
        "POST",
        "/paper/orders",
        token=token,
        json_body={
            "market_id": signal_market_id,
            "side": "SELL",
            "outcome_index": signal_outcome_index,
            "limit_price": str(signal_bid),
            "quantity": str(signal_quantity),
        },
    )
    _require_paper_sell_fill(
        signal_sell_order,
        name="paper_signal_sell_order",
        reference_price=signal_bid,
        expected_signal_id=None,
    )
    checks.append(
        VerificationCheck(
            "paper_signal_sell_order",
            True,
            "signal-created paper position closed at or below displayed bid",
        )
    )

    usage = production_client.request("GET", "/settings/usage", token=token)
    _require_usage_summary(usage)
    checks.append(VerificationCheck("usage", True, "usage counters and job cadence returned"))

    scheduled_count = _require_scheduled_jobs(usage)
    checks.append(
        VerificationCheck(
            "scheduled_jobs",
            True,
            f"{scheduled_count} successful market ingestion job types returned",
        )
    )

    _require_compute_signals_job(usage)
    checks.append(VerificationCheck("compute_signals_job", True, "signal worker job run recorded"))

    _require_manual_refresh_job(usage)
    checks.append(VerificationCheck("manual_refresh_job", True, "manual refresh job run recorded"))

    performance = production_client.request("GET", "/paper/performance", token=token)
    _require_paper_performance(performance)
    checks.append(VerificationCheck("paper_performance", True, "cash, PnL, win rate, and drawdown returned"))

    review = production_client.request("GET", "/paper/review", token=token)
    _require_paper_review(review)
    checks.append(
        VerificationCheck(
            "paper_review",
            True,
            "strategy/category win rate, edge, PnL, drawdown, and trades returned",
        )
    )

    positions = production_client.request("GET", "/paper/positions", token=token)
    position_count = _require_paper_positions(positions)
    checks.append(VerificationCheck("paper_positions", True, f"{position_count} positions returned with PnL fields"))

    trades_csv = production_client.request_text("GET", "/paper/trades.csv", token=token)
    trade_count = _require_trade_traceability(trades_csv)
    checks.append(
        VerificationCheck(
            "paper_trade_traceability",
            True,
            f"{trade_count} trade rows have snapshot and price traceability",
        )
    )

    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify an OddsEye production deployment.")
    parser.add_argument("--base-url", required=True, help="Production API base URL, e.g. https://oddseye.fun")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", help="Admin password. Prefer --password-env for shared shells.")
    parser.add_argument(
        "--password-env",
        default="ODDSEYE_VERIFY_PASSWORD",
        help="Environment variable containing the admin password.",
    )
    args = parser.parse_args(argv)

    password = args.password or os.environ.get(args.password_env)
    if not password:
        parser.error(f"set --password or export {args.password_env}")

    try:
        checks = verify_production(
            base_url=args.base_url,
            username=args.username,
            password=password,
        )
    except ProductionVerificationError as exc:
        print(f"[fail] {exc}", file=sys.stderr)
        return 1

    for check in checks:
        print(f"[ok] {check.name}: {check.detail}")
    return 0


def _require(condition: bool, name: str, message: str) -> None:
    if not condition:
        raise ProductionVerificationError(f"{name}: {message}")


def _require_items(payload: dict[str, Any], name: str) -> int:
    items = payload.get("items")
    _require(isinstance(items, list), name, "missing items list")
    _require(len(items) > 0, name, "expected live items")
    return len(items)


def _require_authenticated_user(payload: dict[str, Any], *, expected_username: str) -> None:
    username = payload.get("username")
    role = payload.get("role")
    _require(username == expected_username, "auth_me", "token resolved to unexpected username")
    _require(isinstance(role, str) and role, "auth_me", "token resolved without role")


def _require_authenticated_endpoints(client: ProductionClient) -> None:
    protected_paths = (
        ("GET", "/auth/me"),
        ("GET", "/radar/markets?limit=1"),
        ("GET", "/signals?limit=1"),
        ("GET", "/paper/positions"),
        ("GET", "/settings/usage"),
    )
    for method, path in protected_paths:
        status_code = client.response_status(method, path)
        _require(
            status_code == 401,
            "auth_required",
            f"{method} {path} returned {status_code}; expected 401 without bearer token",
        )


def _first_market_id(payload: dict[str, Any]) -> str:
    items = payload.get("items")
    _require(isinstance(items, list) and len(items) > 0, "radar", "expected live items")
    market_id = items[0].get("market_id") if isinstance(items[0], dict) else None
    _require(isinstance(market_id, str) and market_id, "radar", "missing market_id")
    return market_id


def _require_market_detail(payload: dict[str, Any]) -> None:
    outcomes = payload.get("outcomes")
    _require(isinstance(outcomes, list) and len(outcomes) > 0, "market_detail", "missing outcomes")
    has_quote = any(
        isinstance(outcome, dict)
        and outcome.get("bid") is not None
        and outcome.get("ask") is not None
        and outcome.get("spread") is not None
        for outcome in outcomes
    )
    _require(has_quote, "market_detail", "missing bid/ask/spread quote")
    _require(payload.get("liquidity_usd") is not None, "market_detail", "missing liquidity")


def _require_freshness(payload: dict[str, Any], name: str) -> None:
    freshness = payload.get("freshness")
    _require(isinstance(freshness, dict), name, "missing freshness object")
    _require(isinstance(freshness.get("is_stale"), bool), name, "missing is_stale boolean")
    age_seconds = freshness.get("age_seconds")
    if age_seconds is not None:
        _require_number(age_seconds, name, "age_seconds")
        _require(float(age_seconds) >= 0, name, "age_seconds must be non-negative")
    last_snapshot_at = freshness.get("last_snapshot_at")
    if last_snapshot_at is not None:
        _require(isinstance(last_snapshot_at, str) and last_snapshot_at, name, "invalid last_snapshot_at")
        _parse_iso_datetime(last_snapshot_at, name, "last_snapshot_at")

    usage_hint = freshness.get("codex_usage_hint")
    _require(isinstance(usage_hint, dict), name, "missing codex_usage_hint")
    for field in ("today_requests", "month_requests"):
        _require(
            isinstance(usage_hint.get(field), int) and not isinstance(usage_hint.get(field), bool),
            name,
            f"missing codex_usage_hint.{field}",
        )
    fetch_profile = usage_hint.get("fetch_profile")
    _require(isinstance(fetch_profile, str) and fetch_profile, name, "missing codex_usage_hint.fetch_profile")


def _require_manual_refresh(payload: dict[str, Any], expected_market_id: str) -> int:
    name = "market_manual_refresh"
    _require(payload.get("market_id") == expected_market_id, name, "market_id mismatch")
    records_processed = payload.get("records_processed")
    _require(
        isinstance(records_processed, int) and not isinstance(records_processed, bool),
        name,
        "missing records_processed",
    )
    _require(records_processed > 0, name, "manual refresh processed no records")
    market = payload.get("market")
    _require(isinstance(market, dict), name, "missing refreshed market")
    _require(market.get("market_id") == expected_market_id, name, "refreshed market_id mismatch")
    _require_freshness(market, name)
    return records_processed


def _first_tradable_quote(payload: dict[str, Any]) -> tuple[int, Decimal, Decimal]:
    outcomes = payload.get("outcomes")
    _require(isinstance(outcomes, list), "paper_manual_order", "missing outcomes")
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            continue
        if outcome.get("bid") is None or outcome.get("ask") is None:
            continue
        index = outcome.get("index")
        _require(isinstance(index, int) and not isinstance(index, bool), "paper_manual_order", "missing outcome index")
        bid = _decimal_payload_value(outcome.get("bid"), "paper_manual_order", "outcome bid")
        ask = _decimal_payload_value(outcome.get("ask"), "paper_manual_order", "outcome ask")
        return index, bid, ask
    raise ProductionVerificationError("paper_manual_order: no tradable bid/ask quote available")


def _tradable_quote_for_outcome(payload: dict[str, Any], outcome_index: int, *, name: str) -> tuple[Decimal, Decimal]:
    outcomes = payload.get("outcomes")
    _require(isinstance(outcomes, list), name, "missing outcomes")
    for outcome in outcomes:
        if not isinstance(outcome, dict) or outcome.get("index") != outcome_index:
            continue
        _require(outcome.get("bid") is not None, name, f"outcome {outcome_index} missing bid")
        _require(outcome.get("ask") is not None, name, f"outcome {outcome_index} missing ask")
        bid = _decimal_payload_value(outcome.get("bid"), name, f"outcome {outcome_index} bid")
        ask = _decimal_payload_value(outcome.get("ask"), name, f"outcome {outcome_index} ask")
        return bid, ask
    raise ProductionVerificationError(f"{name}: no quote for outcome {outcome_index}")


def _require_quality_explanation(payload: dict[str, Any]) -> None:
    name = "market_quality_explanation"
    score = _decimal_payload_value(payload.get("market_quality_score"), name, "market_quality_score")
    _require(Decimal("0") <= score <= Decimal("100"), name, "market_quality_score must be between 0 and 100")

    quality = payload.get("quality")
    _require(isinstance(quality, dict), name, "missing quality object")
    components = quality.get("components")
    _require(isinstance(components, dict), name, "missing quality components")
    missing_components = [component for component in QUALITY_COMPONENT_NAMES if component not in components]
    _require(
        not missing_components,
        name,
        f"missing quality components: {', '.join(missing_components)}",
    )
    for component in QUALITY_COMPONENT_NAMES:
        value = _decimal_payload_value(components.get(component), name, f"quality component {component}")
        _require(
            Decimal("0") <= value <= Decimal("100"),
            name,
            f"quality component {component} must be between 0 and 100",
        )

    reason_codes = quality.get("reason_codes")
    risk_flags = quality.get("risk_flags")
    _require(isinstance(reason_codes, list), name, "missing reason_codes list")
    _require(isinstance(risk_flags, list), name, "missing risk_flags list")
    _require(
        all(isinstance(code, str) and code for code in reason_codes),
        name,
        "reason_codes must contain only non-empty strings",
    )
    _require(
        all(isinstance(flag, str) and flag for flag in risk_flags),
        name,
        "risk_flags must contain only non-empty strings",
    )
    _require(isinstance(quality.get("passes_paper_gate"), bool), name, "missing passes_paper_gate boolean")


def _require_paper_buy_fill(
    payload: dict[str, Any],
    *,
    name: str,
    reference_price: Decimal,
    expected_signal_id: str | None,
) -> None:
    order = payload.get("order")
    fill = payload.get("fill")
    position = payload.get("position")
    _require(isinstance(order, dict), name, "missing order")
    _require(isinstance(fill, dict), name, "missing fill")
    _require(isinstance(position, dict), name, "missing position")
    _require(order.get("status") == "filled", name, "order was not filled")
    if expected_signal_id is None:
        _require(not order.get("signal_id"), name, "manual order unexpectedly has signal_id")
    else:
        _require(order.get("signal_id") == expected_signal_id, name, "order signal_id mismatch")
    _require(fill.get("snapshot_id") is not None, name, "fill missing snapshot_id")
    fill_price = _decimal_payload_value(fill.get("price"), name, "fill price")
    _require(fill_price >= reference_price, name, "BUY fill price is below conservative reference price")


def _require_paper_sell_fill(
    payload: dict[str, Any],
    *,
    name: str,
    reference_price: Decimal,
    expected_signal_id: str | None,
) -> None:
    order = payload.get("order")
    fill = payload.get("fill")
    position = payload.get("position")
    _require(isinstance(order, dict), name, "missing order")
    _require(isinstance(fill, dict), name, "missing fill")
    _require(isinstance(position, dict), name, "missing position")
    _require(order.get("status") == "filled", name, "order was not filled")
    if expected_signal_id is None:
        _require(not order.get("signal_id"), name, "manual order unexpectedly has signal_id")
    else:
        _require(order.get("signal_id") == expected_signal_id, name, "order signal_id mismatch")
    _require(fill.get("snapshot_id") is not None, name, "fill missing snapshot_id")
    fill_price = _decimal_payload_value(fill.get("price"), name, "fill price")
    _require(fill_price <= reference_price, name, "SELL fill price is above conservative reference price")


def _first_orderable_buy_signal(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items")
    _require(isinstance(items, list), "paper_signal_order", "missing BUY signal items")
    for item in items:
        if not isinstance(item, dict):
            continue
        signal_id = item.get("signal_id")
        action = item.get("action")
        side = item.get("side")
        if (
            isinstance(signal_id, str)
            and signal_id
            and action == "BUY"
            and side in {"YES", "NO"}
            and item.get("executable_price") is not None
        ):
            return item
    raise ProductionVerificationError("paper_signal_order: no orderable BUY signal returned")


def _require_signal_action(payload: dict[str, Any], action: str, *, name: str) -> dict[str, Any]:
    items = payload.get("items")
    _require(isinstance(items, list), name, f"missing {action} signal items")
    for item in items:
        if not isinstance(item, dict):
            continue
        signal_id = item.get("signal_id")
        market_id = item.get("market_id")
        question = item.get("question")
        if (
            item.get("action") == action
            and isinstance(signal_id, str)
            and signal_id
            and isinstance(market_id, str)
            and market_id
            and isinstance(question, str)
            and question
        ):
            return item
    raise ProductionVerificationError(f"{name}: no {action} signal returned")


def _require_crypto_threshold_signal(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items")
    _require(isinstance(items, list), "crypto_threshold_signal", "missing crypto signal items")
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("strategy_code") != "crypto_threshold_v1":
            continue
        question = item.get("question")
        category = item.get("category")
        action = item.get("action")
        signal_id = item.get("signal_id")
        market_id = item.get("market_id")
        if (
            isinstance(question, str)
            and question
            and category == "crypto"
            and action in {"BUY", "OBSERVE", "IGNORE", "HOLD", "EXIT"}
            and isinstance(signal_id, str)
            and signal_id
            and isinstance(market_id, str)
            and market_id
            and _looks_like_crypto_threshold_question(question)
        ):
            return item
    raise ProductionVerificationError("crypto_threshold_signal: no crypto_threshold_v1 signal returned")


def _looks_like_crypto_threshold_question(question: str) -> bool:
    upper_question = question.upper()
    has_asset = any(asset in upper_question for asset in CRYPTO_THRESHOLD_ASSETS)
    has_direction = any(word in upper_question for word in ("ABOVE", "BELOW", "OVER", "UNDER", ">"))
    has_number = any(character.isdigit() for character in upper_question)
    return has_asset and has_direction and has_number


def _require_bars(payload: dict[str, Any]) -> int:
    bars = payload.get("bars")
    _require(isinstance(bars, list), "market_bars", "missing bars list")
    _require(len(bars) > 0, "market_bars", "expected chart bars")
    return len(bars)


def _require_radar_sort(payload: dict[str, Any], sort: str) -> int:
    name = f"radar_sort_{sort}"
    items = payload.get("items")
    _require(isinstance(items, list), name, "missing items list")
    _require(len(items) >= 2, name, "expected at least two live items")
    values = [_radar_sort_value(item, sort, name, index) for index, item in enumerate(items, start=1)]
    reverse = sort != "closingSoon"
    _require(
        values == sorted(values, reverse=reverse),
        name,
        f"items are not sorted by {sort}",
    )
    return len(items)


def _radar_sort_value(item: Any, sort: str, name: str, index: int) -> float:
    _require(isinstance(item, dict), name, f"row {index} is not an object")
    if sort == "quality":
        return _numeric_field(item, "market_quality_score", name, index)
    if sort == "volume":
        return _numeric_field(item, "volume_usd_24h", name, index)
    if sort == "liquidity":
        return _numeric_field(item, "liquidity_usd", name, index)
    raw_close = item.get("closes_at")
    _require(isinstance(raw_close, str) and raw_close, name, f"row {index} missing closes_at")
    try:
        return datetime.fromisoformat(raw_close).timestamp()
    except ValueError as exc:
        raise ProductionVerificationError(f"{name}: row {index} has invalid closes_at") from exc


def _numeric_field(item: dict[str, Any], field: str, name: str, index: int) -> float:
    value = item.get(field)
    _require(isinstance(value, int | float) and not isinstance(value, bool), name, f"row {index} missing {field}")
    return float(value)


def _require_usage_summary(payload: dict[str, Any]) -> None:
    for field in ("today_requests", "month_requests"):
        _require(
            isinstance(payload.get(field), int) and not isinstance(payload.get(field), bool),
            "usage",
            f"missing {field}",
        )
    _require(isinstance(payload.get("jobs"), dict), "usage", "missing jobs")


def _require_scheduled_jobs(payload: dict[str, Any]) -> int:
    jobs = payload.get("recent_jobs")
    _require(isinstance(jobs, list), "scheduled_jobs", "missing recent_jobs list")
    successful_jobs = {
        job.get("job_name"): job
        for job in jobs
        if isinstance(job, dict) and job.get("status") == "success" and isinstance(job.get("job_name"), str)
    }
    _require_successful_job(successful_jobs, "discover_events", require_records=False)
    _require_successful_job(successful_jobs, "compute_quality", require_records=False)

    sync_jobs = [job_name for job_name in SYNC_MARKET_JOB_NAMES if job_name in successful_jobs]
    _require(sync_jobs, "scheduled_jobs", "missing successful market sync job")
    for job_name in sync_jobs:
        _require_successful_job(successful_jobs, job_name, require_records=True)
    return 2 + len(sync_jobs)


def _require_manual_refresh_job(payload: dict[str, Any]) -> None:
    jobs = payload.get("recent_jobs")
    _require(isinstance(jobs, list), "manual_refresh_job", "missing recent_jobs list")
    successful_jobs = {
        job.get("job_name"): job
        for job in jobs
        if isinstance(job, dict) and job.get("status") == "success" and isinstance(job.get("job_name"), str)
    }
    _require_successful_job(successful_jobs, "manual_refresh", require_records=True, name="manual_refresh_job")


def _require_compute_signals_job(payload: dict[str, Any]) -> None:
    jobs = payload.get("recent_jobs")
    _require(isinstance(jobs, list), "compute_signals_job", "missing recent_jobs list")
    successful_jobs = {
        job.get("job_name"): job
        for job in jobs
        if isinstance(job, dict) and job.get("status") == "success" and isinstance(job.get("job_name"), str)
    }
    _require_successful_job(successful_jobs, "compute_signals", require_records=True, name="compute_signals_job")


def _require_successful_job(
    jobs_by_name: dict[str, Any],
    job_name: str,
    *,
    require_records: bool,
    name: str = "scheduled_jobs",
) -> None:
    job = jobs_by_name.get(job_name)
    _require(isinstance(job, dict), name, f"missing successful {job_name} job")
    started_at = job.get("started_at")
    finished_at = job.get("finished_at")
    _require(isinstance(started_at, str) and started_at, name, f"{job_name} missing started_at")
    _require(isinstance(finished_at, str) and finished_at, name, f"{job_name} missing finished_at")
    _parse_iso_datetime(started_at, name, f"{job_name} started_at")
    _parse_iso_datetime(finished_at, name, f"{job_name} finished_at")
    records_processed = job.get("records_processed")
    _require(
        isinstance(records_processed, int) and not isinstance(records_processed, bool) and records_processed >= 0,
        name,
        f"{job_name} missing records_processed",
    )
    if require_records:
        _require(records_processed > 0, name, f"{job_name} processed no records")


def _parse_iso_datetime(value: str, name: str, label: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ProductionVerificationError(f"{name}: invalid {label}") from exc


def _require_paper_performance(payload: dict[str, Any]) -> None:
    required_fields = {
        "cash",
        "equity",
        "position_value",
        "realized_pnl",
        "unrealized_pnl",
        "win_rate",
        "max_drawdown",
        "total_trades",
    }
    missing_fields = sorted(required_fields - set(payload))
    _require(not missing_fields, "paper_performance", f"missing keys: {', '.join(missing_fields)}")
    for field in sorted(required_fields):
        _require_number(payload.get(field), "paper_performance", field)


def _require_paper_review(payload: dict[str, Any]) -> None:
    for collection_name in ("strategy_stats", "category_stats"):
        items = payload.get(collection_name)
        _require(isinstance(items, list) and items, "paper_review", f"missing {collection_name}")
        for index, item in enumerate(items, start=1):
            _require(isinstance(item, dict), "paper_review", f"{collection_name} row {index} is not an object")
            key = item.get("key")
            _require(isinstance(key, str) and key, "paper_review", f"{collection_name} row {index} missing key")
            for field in ("total_trades", "total_notional", "realized_pnl", "win_rate", "max_drawdown"):
                _require_number(item.get(field), "paper_review", f"{collection_name} row {index} {field}")
            average_edge = item.get("average_edge")
            if average_edge is not None:
                _require_number(average_edge, "paper_review", f"{collection_name} row {index} average_edge")
    trades = payload.get("trades")
    _require(isinstance(trades, list) and trades, "paper_review", "missing trades")


def _require_paper_positions(payload: dict[str, Any]) -> int:
    items = payload.get("items")
    _require(isinstance(items, list), "paper_positions", "missing items list")
    _require(len(items) > 0, "paper_positions", "expected at least one position")
    for index, item in enumerate(items, start=1):
        _require(isinstance(item, dict), "paper_positions", f"row {index} is not an object")
        for field in ("position_id", "market_id", "status"):
            value = item.get(field)
            _require(isinstance(value, str) and value, "paper_positions", f"row {index} missing {field}")
        outcome_index = item.get("outcome_index")
        _require(
            isinstance(outcome_index, int) and not isinstance(outcome_index, bool),
            "paper_positions",
            f"row {index} missing outcome_index",
        )
        for field in ("quantity", "avg_price", "realized_pnl", "unrealized_pnl"):
            _require_number(item.get(field), "paper_positions", f"row {index} {field}")
        if item.get("status") == "open":
            _require_number(item.get("mark_price"), "paper_positions", f"row {index} mark_price")
    return len(items)


def _require_number(value: Any, name: str, label: str) -> None:
    _require(isinstance(value, int | float) and not isinstance(value, bool), name, f"missing numeric {label}")


def _decimal_payload_value(value: Any, name: str, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ProductionVerificationError(f"{name}: missing {label}")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ProductionVerificationError(f"{name}: invalid {label}") from exc


def _require_trade_traceability(csv_text: str) -> int:
    reader = csv.DictReader(StringIO(csv_text))
    fieldnames = set(reader.fieldnames or [])
    required_columns = {"fill_id", "order_id", "signal_id", "snapshot_id", "price"}
    missing_columns = sorted(required_columns - fieldnames)
    _require(
        not missing_columns,
        "paper_trade_traceability",
        f"missing columns: {', '.join(missing_columns)}",
    )

    row_count = 0
    for row_count, row in enumerate(reader, start=1):
        snapshot_id = (row.get("snapshot_id") or "").strip()
        price = (row.get("price") or "").strip()
        signal_id = (row.get("signal_id") or "").strip()
        strategy_code = (row.get("strategy_code") or "").strip()
        _require(
            bool(snapshot_id),
            "paper_trade_traceability",
            f"row {row_count} missing snapshot_id",
        )
        _require(
            _is_number(price),
            "paper_trade_traceability",
            f"row {row_count} missing numeric price",
        )
        if strategy_code:
            _require(
                bool(signal_id),
                "paper_trade_traceability",
                f"row {row_count} missing signal_id for strategy trade",
            )
    return row_count


def _is_number(value: str) -> bool:
    if not value:
        return False
    try:
        float(value)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
