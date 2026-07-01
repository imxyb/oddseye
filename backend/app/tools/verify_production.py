from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any, Protocol

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


if __name__ == "__main__":
    raise SystemExit(main())
