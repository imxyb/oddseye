from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from datetime import datetime
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

    radar = production_client.request("GET", "/radar/markets?limit=3", token=token)
    radar_count = _require_items(radar, "radar")
    checks.append(VerificationCheck("radar", True, f"{radar_count} markets returned"))

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

    bars = production_client.request(
        "GET",
        f"/markets/{encoded_market_id}/bars?range=7d&resolution=hour1",
        token=token,
    )
    bar_count = _require_bars(bars)
    checks.append(VerificationCheck("market_bars", True, f"{bar_count} bars returned"))

    signals = production_client.request("GET", "/signals?limit=3", token=token)
    signal_count = _require_items(signals, "signals")
    checks.append(VerificationCheck("signals", True, f"{signal_count} signals returned"))

    usage = production_client.request("GET", "/settings/usage", token=token)
    _require("today_requests" in usage, "usage", "missing today_requests")
    _require(isinstance(usage.get("jobs"), dict), "usage", "missing jobs")
    checks.append(VerificationCheck("usage", True, "usage counters and job cadence returned"))

    performance = production_client.request("GET", "/paper/performance", token=token)
    required_performance_keys = {"cash", "equity", "win_rate", "max_drawdown", "total_trades"}
    missing_keys = sorted(required_performance_keys - set(performance))
    _require(not missing_keys, "paper_performance", f"missing keys: {', '.join(missing_keys)}")
    checks.append(VerificationCheck("paper_performance", True, "paper account metrics returned"))

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
