from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.normalizer.prediction_market import coerce_token_ids


@dataclass(frozen=True)
class PolymarketMarketTokens:
    condition_id: str
    token_ids: list[str]
    raw_json: dict[str, Any]


class PolymarketMarketMetadataClient:
    def __init__(
        self,
        base_url: str = "https://gamma-api.polymarket.com",
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: int = 5,
    ):
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.AsyncClient(timeout=timeout_seconds, trust_env=False)
        self._owns_http_client = http_client is None

    async def get_market_tokens(
        self,
        external_market_id: str,
        raw_json: dict[str, Any],
    ) -> PolymarketMarketTokens | None:
        condition_id = _condition_id(external_market_id, raw_json)
        if not condition_id:
            return None
        response = await self.http_client.get(
            f"{self.base_url}/markets",
            params={"condition_ids": condition_id},
        )
        response.raise_for_status()
        market = _select_market(response.json(), condition_id)
        if not market:
            return None
        token_ids = _market_token_ids(market)
        if len(token_ids) < 2:
            return None
        return PolymarketMarketTokens(
            condition_id=condition_id,
            token_ids=token_ids[:2],
            raw_json=market,
        )

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self.http_client.aclose()


def _condition_id(external_market_id: str, raw_json: dict[str, Any]) -> str | None:
    for value in (
        _condition_id_from_raw(raw_json),
        _condition_id_from_raw(raw_json.get("market") if isinstance(raw_json.get("market"), dict) else {}),
        _condition_id_from_external_id(external_market_id),
    ):
        if value:
            return value
    return None


def _condition_id_from_raw(raw: dict[str, Any]) -> str | None:
    for key in ("conditionId", "condition_id", "conditionID"):
        value = raw.get(key)
        if value:
            return str(value)
    return None


def _condition_id_from_external_id(external_market_id: str) -> str | None:
    first_part = str(external_market_id).split(":", 1)[0].strip()
    if first_part.startswith("0x") and len(first_part) >= 10:
        return first_part
    return None


def _select_market(data: Any, condition_id: str) -> dict[str, Any] | None:
    if isinstance(data, dict):
        candidates = data.get("markets") or data.get("data") or data.get("results")
        if isinstance(candidates, list):
            return _select_market(candidates, condition_id)
        return data if _matches_condition_id(data, condition_id) else None
    if not isinstance(data, list):
        return None
    for market in data:
        if isinstance(market, dict) and _matches_condition_id(market, condition_id):
            return market
    first_market = data[0] if data and isinstance(data[0], dict) else None
    return first_market


def _matches_condition_id(market: dict[str, Any], condition_id: str) -> bool:
    return any(
        str(market.get(key) or "").lower() == condition_id.lower()
        for key in ("conditionId", "condition_id", "conditionID")
    )


def _market_token_ids(market: dict[str, Any]) -> list[str]:
    for key in ("clobTokenIds", "clob_token_ids", "tokenIds", "token_ids"):
        token_ids = coerce_token_ids(market.get(key))
        if len(token_ids) >= 2:
            return token_ids
    tokens = market.get("tokens")
    token_ids = coerce_token_ids(tokens)
    return token_ids if len(token_ids) >= 2 else []
