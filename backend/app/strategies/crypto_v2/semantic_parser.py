from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

import httpx

SEMANTIC_CACHE_KEY = "crypto_v2_semantic_parse"
SEMANTIC_CACHE_VERSION = "llm_semantic_v1"
SEMANTIC_MARKET_TYPES = {
    "close_above",
    "close_below",
    "hit_above",
    "hit_below",
    "range_close",
    "range_touch",
}


class SemanticParseError(RuntimeError):
    pass


class SemanticParser(Protocol):
    def parse(
        self,
        *,
        question: str,
        event_question: str | None,
        resolution_source: str | None,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class DeepSeekSemanticParser:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float
    http_client: httpx.Client | None = None

    def parse(
        self,
        *,
        question: str,
        event_question: str | None,
        resolution_source: str | None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise SemanticParseError("missing_deepseek_api_key")
        client = self.http_client or httpx.Client(timeout=self.timeout_seconds, trust_env=False)
        response = client.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "question": question,
                                "event_question": event_question,
                                "resolution_source": resolution_source,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,
                "max_tokens": 500,
            },
        )
        response.raise_for_status()
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise SemanticParseError("deepseek_response_missing_content") from exc
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise SemanticParseError("deepseek_response_not_json") from exc
        return normalize_semantic_payload(payload)


def normalize_semantic_payload(payload: dict[str, Any]) -> dict[str, Any]:
    market_type = str(payload.get("market_type") or "").strip().lower()
    if market_type not in SEMANTIC_MARKET_TYPES:
        raise SemanticParseError("unsupported_semantic_market_type")
    normalized: dict[str, Any] = {
        "asset": _upper_or_none(payload.get("asset")),
        "market_type": market_type,
        "threshold": _decimal_string_or_none(payload.get("threshold")),
        "lower_threshold": _decimal_string_or_none(payload.get("lower_threshold")),
        "upper_threshold": _decimal_string_or_none(payload.get("upper_threshold")),
        "settlement": str(payload.get("settlement") or "").strip().lower() or None,
        "confidence": _float_or_zero(payload.get("confidence")),
        "unsupported_flags": [
            str(flag).strip().upper()
            for flag in payload.get("unsupported_flags") or []
            if str(flag).strip()
        ],
    }
    return normalized


def cache_payload(
    *,
    question: str,
    resolution_source: str | None,
    provider: str,
    model: str,
    parsed: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": SEMANTIC_CACHE_VERSION,
        "question": question,
        "resolution_source": resolution_source,
        "provider": provider,
        "model": model,
        "parsed": parsed,
    }


def semantic_from_cache(
    raw_json: dict[str, Any] | None,
    *,
    question: str,
    resolution_source: str | None,
) -> dict[str, Any] | None:
    cached = (raw_json or {}).get(SEMANTIC_CACHE_KEY)
    if not isinstance(cached, dict):
        return None
    if cached.get("version") != SEMANTIC_CACHE_VERSION:
        return None
    if cached.get("question") != question:
        return None
    if cached.get("resolution_source") != resolution_source:
        return None
    parsed = cached.get("parsed")
    if not isinstance(parsed, dict):
        return None
    try:
        return normalize_semantic_payload(parsed)
    except SemanticParseError:
        return None


def _upper_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def _decimal_string_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        return str(Decimal(str(value).replace(",", "")))
    except (InvalidOperation, ValueError):
        return None


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


_SYSTEM_PROMPT = """\
You classify crypto prediction-market questions into strict JSON for a trading parser.
Return JSON only with this schema:
{
  "asset": "BTC" | "ETH" | "SOL" | null,
  "market_type": "close_above" | "close_below" | "hit_above" | "hit_below" | "range_close" | "range_touch",
  "threshold": string | null,
  "lower_threshold": string | null,
  "upper_threshold": string | null,
  "settlement": "close_at_deadline" | "touch_intraperiod" | "range_close" | "range_touch" | "unknown",
  "confidence": number,
  "unsupported_flags": string[]
}

Rules:
- "dip to", "fall to", "drop to", "trade down to" are hit_below.
- "reach", "hit", "touch", "trade at" a single upper price are hit_above unless the wording says down/dip/fall/drop/below/under.
- "above/over at/on/by close" is close_above unless the wording says hit/touch/reach before the deadline.
- "below/under at/on/by close" is close_below unless the wording says hit/touch/reach/dip/fall/drop before the deadline.
- "between X and Y at close" is range_close.
- "touch either X or Y", "hit either X or Y", or any two-sided intraperiod barrier is range_touch.
- If the question is not a spot-price BTC/ETH/SOL threshold market, include a concise unsupported flag.
"""
