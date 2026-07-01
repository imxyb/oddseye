from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


AMBIGUOUS_WORDS = {"substantially", "significant", "major", "soon", "roughly", "approximately"}
MODELABLE_CRYPTO = {"BTC", "BITCOIN", "ETH", "ETHEREUM", "SOL", "SOLANA"}
MODELABLE_MACRO = {"CPI", "FOMC", "FED", "RATE", "UNEMPLOYMENT", "INFLATION"}
SUPPORTED_CATEGORIES = {"crypto", "economics", "finance", "macro"}


@dataclass(frozen=True)
class QualityInputs:
    question: str
    description: str | None
    categories: list[str]
    status: str
    venue_url: str | None
    closes_at: datetime | None
    resolves_at: datetime | None
    liquidity_usd: float | None
    spread_ct: float | None
    volume_usd_24h: float | None
    trades_24h: float | None


@dataclass(frozen=True)
class QualityResult:
    score: float
    components: dict[str, float]
    reason_codes: list[str]
    risk_flags: list[str]
    passes_paper_gate: bool


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def liquidity_score(liquidity_usd: float | None) -> float:
    if liquidity_usd is None:
        return 0
    return clamp((liquidity_usd - 1_000) / (50_000 - 1_000) * 100)


def spread_score(spread_ct: float | None) -> float:
    if spread_ct is None:
        return 0
    return clamp((0.10 - spread_ct) / (0.10 - 0.02) * 100)


def activity_score(volume_usd_24h: float | None, trades_24h: float | None) -> float:
    volume_part = clamp((volume_usd_24h or 0) / 20_000 * 100)
    trades_part = clamp((trades_24h or 0) / 200 * 100)
    return 0.7 * volume_part + 0.3 * trades_part


def resolution_clarity_score(inputs: QualityInputs, now: datetime) -> float:
    score = 0.0
    if inputs.resolves_at is not None and inputs.closes_at is not None and inputs.venue_url:
        score += 30
    words = {word.strip(" ,.!?;:").lower() for word in inputs.question.split()}
    if not words.intersection(AMBIGUOUS_WORDS):
        score += 20
    if inputs.description and len(inputs.description) > 100:
        score += 20
    categories = {category.lower() for category in inputs.categories}
    if categories.intersection(SUPPORTED_CATEGORIES):
        score += 10
    if inputs.status.upper() == "OPEN" and inputs.resolves_at and inputs.resolves_at > now:
        score += 20
    return clamp(score)


def modelability_score(question: str, categories: list[str]) -> float:
    upper = question.upper()
    categories_lower = {category.lower() for category in categories}
    if any(asset in upper for asset in MODELABLE_CRYPTO) and any(
        keyword in upper for keyword in ("ABOVE", "BELOW", "HIT", "$")
    ):
        return 90
    if any(keyword in upper for keyword in MODELABLE_MACRO):
        return 70
    if "crypto" in categories_lower:
        return 40
    if categories_lower.intersection({"politics", "sports", "entertainment"}):
        return 20
    return 30


def time_score(closes_at: datetime | None, now: datetime) -> float:
    if closes_at is None:
        return 0
    delta = closes_at - now
    if delta <= timedelta(minutes=30):
        return 0
    if delta <= timedelta(days=1):
        return 45
    if delta <= timedelta(days=60):
        return 100
    if delta <= timedelta(days=365):
        return 65
    return 30


def compute_market_quality(inputs: QualityInputs, now: datetime) -> QualityResult:
    components = {
        "liquidity": liquidity_score(inputs.liquidity_usd),
        "spread": spread_score(inputs.spread_ct),
        "resolution_clarity": resolution_clarity_score(inputs, now),
        "modelability": modelability_score(inputs.question, inputs.categories),
        "time": time_score(inputs.closes_at, now),
        "activity": activity_score(inputs.volume_usd_24h, inputs.trades_24h),
    }
    risk_flags: list[str] = []
    reason_codes: list[str] = []
    if (inputs.liquidity_usd or 0) < 1_000:
        risk_flags.append("LOW_LIQUIDITY")
    else:
        reason_codes.append("LIQUIDITY_OK")
    if inputs.spread_ct is None or inputs.spread_ct > 0.08:
        risk_flags.append("WIDE_SPREAD")
    else:
        reason_codes.append("SPREAD_OK")
    if inputs.status.upper() != "OPEN":
        risk_flags.append("NOT_OPEN")
    if inputs.closes_at is None or inputs.closes_at <= now + timedelta(minutes=30):
        risk_flags.append("CLOSES_TOO_SOON")
    if components["resolution_clarity"] < 60:
        risk_flags.append("RESOLUTION_UNCLEAR")
    if components["modelability"] < 60:
        risk_flags.append("LOW_MODELABILITY")

    risk_penalty = 8 * len(risk_flags)
    score = (
        0.25 * components["liquidity"]
        + 0.20 * components["spread"]
        + 0.20 * components["resolution_clarity"]
        + 0.15 * components["modelability"]
        + 0.10 * components["time"]
        + 0.10 * components["activity"]
        - risk_penalty
    )
    score = clamp(score)
    passes_gate = (
        score >= 65
        and (inputs.liquidity_usd or 0) >= 1_000
        and (inputs.volume_usd_24h or 0) >= 500
        and inputs.spread_ct is not None
        and inputs.spread_ct <= 0.08
        and inputs.status.upper() == "OPEN"
        and inputs.closes_at is not None
        and inputs.closes_at > now + timedelta(minutes=30)
        and components["modelability"] >= 60
        and components["resolution_clarity"] >= 60
    )
    return QualityResult(
        score=round(score, 4),
        components={key: round(value, 4) for key, value in components.items()},
        reason_codes=reason_codes,
        risk_flags=risk_flags,
        passes_paper_gate=passes_gate,
    )

