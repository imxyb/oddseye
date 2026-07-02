from __future__ import annotations

import re
from functools import lru_cache
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.config import get_settings
from app.strategies.crypto_v2.spec import CryptoMarketSpec, ParseResult
from app.strategies.crypto_v2.semantic_parser import (
    SEMANTIC_CACHE_KEY,
    DeepSeekSemanticParser,
    SemanticParseError,
    SemanticParser,
    cache_payload,
    normalize_semantic_payload,
    semantic_from_cache,
)

ASSET_ALIASES = {
    "BTC": "BTC",
    "BITCOIN": "BTC",
    "ETH": "ETH",
    "ETHEREUM": "ETH",
    "SOL": "SOL",
    "SOLANA": "SOL",
}
ASSET_PATTERN = re.compile(r"\b(BTC|BITCOIN|ETH|ETHEREUM|SOL|SOLANA)\b", re.IGNORECASE)
PRICE_PATTERN = re.compile(
    r"(?:\$\s*)?([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)"
    r"\s*(?:(k|m|b|t)\b|(usd|usdt|dollars?)\b)?",
    re.IGNORECASE,
)
MONTH_PATTERN = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+([0-9]{1,2})(?:st|nd|rd|th)?(?:,\s*([0-9]{4}))?\b",
    re.IGNORECASE,
)
MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


class CryptoMarketSpecParserV2:
    def __init__(self, semantic_parser: SemanticParser | None = None):
        self.semantic_parser = semantic_parser

    def parse(self, market: Any, event: Any | None = None) -> ParseResult:
        question = str(getattr(market, "question", "") or "")
        upper = question.upper()
        flags: list[str] = []
        raw_parse: dict[str, Any] = {"question": question}
        settings = get_settings()
        parser_config = settings.config.strategies.crypto_threshold_v2.parser
        semantic, semantic_error = self._semantic_parse(
            market,
            event,
            settings=settings,
            provider_name=parser_config.semantic_provider,
            live_parse_enabled=parser_config.semantic_live_parse_enabled,
        )
        if semantic is not None:
            raw_parse["semantic_parse"] = semantic
        if semantic_error is not None:
            raw_parse["semantic_error"] = semantic_error

        assets = _extract_assets(question)
        if not assets:
            flags.append("NO_ASSET")
        if len(assets) > 1:
            flags.append("MULTI_ASSET_CONDITION")

        if "MARKET CAP" in upper:
            flags.append("MARKET_CAP_METRIC")
        if "ETF" in upper or "INFLOW" in upper:
            flags.append("ETF_FLOW_METRIC")
        if "FUNDING" in upper:
            flags.append("FUNDING_RATE_METRIC")
        if "ALL-TIME HIGH" in upper or "ALL TIME HIGH" in upper or re.search(r"\bATH\b", upper):
            flags.append("ATH_REQUIRES_HISTORY")

        thresholds = _extract_thresholds(question)
        regex_market_type = _market_type(upper, len(thresholds))
        market_type = _semantic_market_type(
            semantic,
            min_confidence=parser_config.semantic_min_confidence,
        ) or regex_market_type
        if semantic is not None:
            flags.extend(_semantic_flags(semantic, assets, thresholds, parser_config.semantic_min_confidence))
        elif _llm_semantics_required(settings, parser_config.semantic_provider, self.semantic_parser):
            flags.append("LLM_SEMANTIC_PARSE_UNAVAILABLE")

        if market_type == "range_touch":
            flags.append("RANGE_TOUCH_UNSUPPORTED")
            if len(thresholds) < 2:
                flags.append("NO_THRESHOLD")
            lower_threshold, upper_threshold = sorted(thresholds[:2]) if len(thresholds) >= 2 else (None, None)
            threshold = None
        elif market_type == "range_close":
            if len(thresholds) < 2:
                flags.append("NO_THRESHOLD")
            lower_threshold, upper_threshold = sorted(thresholds[:2]) if len(thresholds) >= 2 else (None, None)
            threshold = None
        else:
            if not thresholds:
                flags.append("NO_THRESHOLD")
            threshold = thresholds[0] if thresholds else None
            lower_threshold = None
            upper_threshold = None

        record_deadline = _deadline_from_market(market, event)
        parsed_deadline = _parse_deadline(question)
        window_end = record_deadline or parsed_deadline
        if window_end is None:
            flags.append("NO_DEADLINE")
        elif record_deadline is None and parsed_deadline is not None:
            flags.append("UNCLEAR_TIMEZONE")

        resolution_source = getattr(market, "resolution_source", None)
        if not resolution_source:
            flags.append("UNCLEAR_RESOLUTION_SOURCE")

        if flags:
            return ParseResult(spec=None, ambiguity_flags=flags, raw_parse=raw_parse)

        asset = next(iter(assets))
        confidence = _confidence(market_type, resolution_source)
        spec = CryptoMarketSpec(
            market_id=str(getattr(market, "id")),
            event_id=str(getattr(event, "id", getattr(market, "event_id", "")) or "") or None,
            protocol=str(getattr(market, "protocol", getattr(event, "protocol", "POLYMARKET")) or "POLYMARKET").upper(),
            question=question,
            asset=asset,
            quote_currency="USDT",
            metric="spot_price",
            market_type=market_type,
            threshold=threshold,
            lower_threshold=lower_threshold,
            upper_threshold=upper_threshold,
            window_start=None,
            window_end=window_end,
            settlement_time=None,
            settlement_timezone="UTC",
            resolution_source=resolution_source,
            parser_confidence=confidence,
            ambiguity_flags=[],
            raw_parse={
                **raw_parse,
                "thresholds": [str(value) for value in thresholds],
                "regex_market_type": regex_market_type,
                "source": "llm_semantic_v1" if semantic is not None else "regex_v2",
            },
        )
        return ParseResult(spec=spec, ambiguity_flags=[], raw_parse=spec.raw_parse)

    def _semantic_parse(
        self,
        market: Any,
        event: Any | None,
        *,
        settings: Any,
        provider_name: str,
        live_parse_enabled: bool,
    ) -> tuple[dict[str, Any] | None, str | None]:
        question = str(getattr(market, "question", "") or "")
        resolution_source = getattr(market, "resolution_source", None)
        cached = semantic_from_cache(
            getattr(market, "raw_json", None),
            question=question,
            resolution_source=resolution_source,
        )
        if cached is not None:
            return cached, None

        parser = self.semantic_parser
        provider = "test"
        model = "test"
        if parser is None:
            if provider_name != "deepseek" or not settings.deepseek_api_key or not live_parse_enabled:
                return None, None
            provider = "deepseek"
            model = settings.deepseek_model
            parser = _deepseek_parser(
                settings.deepseek_api_key,
                settings.deepseek_base_url,
                settings.deepseek_model,
                settings.deepseek_timeout_seconds,
            )
        try:
            parsed = normalize_semantic_payload(
                parser.parse(
                    question=question,
                    event_question=getattr(event, "question", None),
                    resolution_source=resolution_source,
                )
            )
        except (SemanticParseError, ValueError, TypeError) as exc:
            return None, str(exc)
        _store_semantic_cache(
            market,
            cache_payload(
                question=question,
                resolution_source=resolution_source,
                provider=provider,
                model=model,
                parsed=parsed,
            ),
        )
        return parsed, None


def _extract_assets(question: str) -> set[str]:
    return {ASSET_ALIASES[match.group(1).upper()] for match in ASSET_PATTERN.finditer(question)}


def _extract_thresholds(question: str) -> list[Decimal]:
    thresholds: list[Decimal] = []
    for match in PRICE_PATTERN.finditer(question):
        token = match.group(0)
        suffix = (match.group(2) or match.group(3) or "").lower()
        if not _looks_like_price(token, suffix):
            continue
        value = Decimal(match.group(1).replace(",", ""))
        multiplier = {
            "k": Decimal("1000"),
            "m": Decimal("1000000"),
            "b": Decimal("1000000000"),
            "t": Decimal("1000000000000"),
        }.get(suffix, Decimal("1"))
        thresholds.append(value * multiplier)
    return thresholds


def _semantic_market_type(semantic: dict[str, Any] | None, min_confidence: float) -> str | None:
    if semantic is None:
        return None
    if float(semantic.get("confidence") or 0) < min_confidence:
        return None
    market_type = semantic.get("market_type")
    return str(market_type) if market_type else None


def _semantic_flags(
    semantic: dict[str, Any],
    assets: set[str],
    thresholds: list[Decimal],
    min_confidence: float,
) -> list[str]:
    flags: list[str] = []
    if float(semantic.get("confidence") or 0) < min_confidence:
        flags.append("LLM_SEMANTIC_LOW_CONFIDENCE")
    flags.extend(str(flag) for flag in semantic.get("unsupported_flags") or [])
    semantic_asset = semantic.get("asset")
    if semantic_asset is not None and assets and semantic_asset not in assets:
        flags.append("LLM_PARSE_CONFLICT")
    semantic_thresholds = _semantic_threshold_values(semantic)
    if semantic_thresholds and thresholds and any(value not in thresholds for value in semantic_thresholds):
        flags.append("LLM_PARSE_CONFLICT")
    return _dedupe(flags)


def _semantic_threshold_values(semantic: dict[str, Any]) -> list[Decimal]:
    values: list[Decimal] = []
    for key in ("threshold", "lower_threshold", "upper_threshold"):
        value = semantic.get(key)
        if value in (None, ""):
            continue
        try:
            values.append(Decimal(str(value).replace(",", "")))
        except (InvalidOperation, ValueError):
            continue
    return values


def _llm_semantics_required(settings: Any, provider_name: str, semantic_parser: SemanticParser | None) -> bool:
    if semantic_parser is not None:
        return True
    return provider_name == "deepseek" and bool(settings.deepseek_api_key)


def _store_semantic_cache(market: Any, payload: dict[str, Any]) -> None:
    if not hasattr(market, "raw_json"):
        return
    raw = dict(getattr(market, "raw_json", None) or {})
    raw[SEMANTIC_CACHE_KEY] = payload
    market.raw_json = raw


@lru_cache(maxsize=4)
def _deepseek_parser(
    api_key: str,
    base_url: str,
    model: str,
    timeout_seconds: float,
) -> DeepSeekSemanticParser:
    return DeepSeekSemanticParser(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
    )


def _looks_like_price(token: str, suffix: str) -> bool:
    return (
        "$" in token
        or "," in token
        or suffix in {"k", "m", "b", "t", "usd", "usdt", "dollar", "dollars"}
    )


def _market_type(question_upper: str, threshold_count: int) -> str:
    hit = any(word in question_upper for word in ("HIT", "TOUCH", "REACH", "TRADE AT", "FALL", "DIP"))
    if hit and threshold_count >= 2:
        return "range_touch"
    if "BETWEEN" in question_upper or " RANGE " in f" {question_upper} ":
        return "range_close"
    below = any(word in question_upper for word in ("BELOW", "UNDER", "LESS THAN", "FALL", "DIP", "DROP"))
    if hit and below:
        return "hit_below"
    if hit:
        return "hit_above"
    if below:
        return "close_below"
    return "close_above"


def _deadline_from_market(market: Any, event: Any | None) -> datetime | None:
    value = getattr(market, "closes_at", None) or getattr(event, "closes_at", None)
    if value is None:
        return None
    return _as_aware(value)


def _parse_deadline(question: str) -> datetime | None:
    match = MONTH_PATTERN.search(question)
    if not match:
        return None
    year = int(match.group(3) or datetime.now(UTC).year)
    month = MONTHS[match.group(1).lower()]
    day = int(match.group(2))
    return datetime(year, month, day, 23, 59, 59, tzinfo=UTC)


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _confidence(market_type: str, resolution_source: str | None) -> float:
    base = 0.93 if market_type in {"hit_above", "hit_below"} else 0.90
    if not resolution_source:
        base -= 0.05
    return base


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
