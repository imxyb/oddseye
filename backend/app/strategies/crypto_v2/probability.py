from __future__ import annotations

import math
import random
import statistics
from decimal import Decimal

from app.strategies.crypto_v2.calibration import blend_with_market_prior, clamp, default_calibrate
from app.strategies.crypto_v2.spec import CryptoAssetSnapshot, CryptoMarketSpec, ProbabilityEstimate

SECONDS_PER_YEAR = 365.25 * 24 * 60 * 60


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def realized_vol_from_closes(closes: list[Decimal], periods_per_year: int) -> float:
    returns = [
        math.log(float(closes[index] / closes[index - 1]))
        for index in range(1, len(closes))
        if closes[index - 1] > 0 and closes[index] > 0
    ]
    if len(returns) < 2:
        return 0.0
    return statistics.stdev(returns) * math.sqrt(periods_per_year)


def close_above_probability(
    spot: float,
    threshold: float,
    years_to_expiry: float,
    annualized_vol: float,
    drift: float = 0.0,
) -> float:
    if years_to_expiry <= 0:
        return 1.0 if spot > threshold else 0.0
    sigma = max(annualized_vol, 1e-9)
    z = (
        math.log(spot / threshold)
        + (drift - 0.5 * sigma * sigma) * years_to_expiry
    ) / (sigma * math.sqrt(years_to_expiry))
    return clamp(normal_cdf(z), 0.0, 1.0)


def close_below_probability(
    spot: float,
    threshold: float,
    years_to_expiry: float,
    annualized_vol: float,
    drift: float = 0.0,
) -> float:
    return 1.0 - close_above_probability(spot, threshold, years_to_expiry, annualized_vol, drift)


def range_close_probability(
    spot: float,
    lower_threshold: float,
    upper_threshold: float,
    years_to_expiry: float,
    annualized_vol: float,
    drift: float = 0.0,
) -> float:
    if lower_threshold > upper_threshold:
        lower_threshold, upper_threshold = upper_threshold, lower_threshold
    p_above_lower = close_above_probability(
        spot, lower_threshold, years_to_expiry, annualized_vol, drift
    )
    p_above_upper = close_above_probability(
        spot, upper_threshold, years_to_expiry, annualized_vol, drift
    )
    return clamp(p_above_lower - p_above_upper, 0.0, 1.0)


def touch_probability_mc(
    spot: float,
    threshold: float,
    years_to_expiry: float,
    annualized_vol: float,
    direction: str,
    drift: float = 0.0,
    n_paths: int = 20_000,
    n_steps: int | None = None,
    seed: int = 42,
) -> float:
    if years_to_expiry <= 0:
        if direction == "above":
            return 1.0 if spot >= threshold else 0.0
        return 1.0 if spot <= threshold else 0.0
    if direction == "above" and spot >= threshold:
        return 1.0
    if direction == "below" and spot <= threshold:
        return 1.0

    steps = n_steps or choose_mc_steps(years_to_expiry * 365.25 * 24)
    dt = years_to_expiry / max(steps, 1)
    sigma = max(annualized_vol, 1e-9)
    drift_step = (drift - 0.5 * sigma * sigma) * dt
    vol_step = sigma * math.sqrt(dt)
    rng = random.Random(seed)
    hits = 0
    total = 0
    pairs = max(n_paths // 2, 1)
    for _ in range(pairs):
        shocks = [rng.gauss(0.0, 1.0) for _ in range(steps)]
        for sign in (1.0, -1.0):
            price = spot
            hit = False
            for shock in shocks:
                price *= math.exp(drift_step + vol_step * shock * sign)
                if (direction == "above" and price >= threshold) or (
                    direction == "below" and price <= threshold
                ):
                    hit = True
                    break
            total += 1
            if hit:
                hits += 1
    mc_probability = hits / total
    terminal_probability = (
        close_above_probability(spot, threshold, years_to_expiry, annualized_vol, drift)
        if direction == "above"
        else close_below_probability(spot, threshold, years_to_expiry, annualized_vol, drift)
    )
    return clamp(max(mc_probability, terminal_probability), 0.0, 1.0)


def choose_mc_steps(horizon_hours: float) -> int:
    if horizon_hours <= 6:
        return max(24, int(horizon_hours * 12))
    if horizon_hours <= 48:
        return max(48, int(horizon_hours * 4))
    if horizon_hours <= 24 * 14:
        return max(96, int(horizon_hours))
    return min(720, max(1, int(horizon_hours / 4)))


def estimate_probability(
    spec: CryptoMarketSpec,
    snapshot: CryptoAssetSnapshot,
    *,
    now,
    market_mid: float | None,
    spread: float | None,
    mc_paths: int = 20_000,
    mc_seed: int = 42,
) -> ProbabilityEstimate:
    horizon_hours = max((spec.window_end - now).total_seconds() / 3600, 0.0)
    years = max((spec.window_end - now).total_seconds(), 0.0) / SECONDS_PER_YEAR
    selected_vol = select_horizon_vol(snapshot, horizon_hours)

    def raw_for_vol(vol: float) -> float:
        return _raw_probability(spec, snapshot, years, vol, horizon_hours, mc_paths, mc_seed)

    p_model = raw_for_vol(selected_vol)
    p_after_trend = clamp(p_model + trend_adjustment(snapshot, spec.asset, spec.market_type), 0.0, 1.0)
    p_calibrated, uncertainty_penalty = default_calibrate(
        p_after_trend,
        data_quality=_data_quality(snapshot),
        market_type=spec.market_type,
    )
    p_trade = blend_with_market_prior(
        p_calibrated,
        p_market_mid=market_mid,
        spread=spread,
        model_confidence=spec.parser_confidence,
    )
    p_low_raw = clamp(
        raw_for_vol(selected_vol * 0.85)
        + trend_adjustment(snapshot, spec.asset, spec.market_type),
        0.0,
        1.0,
    )
    p_high_raw = clamp(
        raw_for_vol(selected_vol * 1.15)
        + trend_adjustment(snapshot, spec.asset, spec.market_type),
        0.0,
        1.0,
    )
    p_low, _ = default_calibrate(p_low_raw, _data_quality(snapshot), spec.market_type)
    p_high, _ = default_calibrate(p_high_raw, _data_quality(snapshot), spec.market_type)
    model_family = "touch_barrier_mc_v2" if spec.market_type.startswith("hit_") else "close_lognormal_v2"
    return ProbabilityEstimate(
        p_raw=p_model,
        p_calibrated=p_trade,
        p_low=p_low,
        p_high=p_high,
        model_family=model_family,
        confidence=clamp(spec.parser_confidence * _data_quality(snapshot), 0.0, 1.0),
        uncertainty_penalty=uncertainty_penalty,
        diagnostics={
            "selected_vol": selected_vol,
            "horizon_hours": horizon_hours,
            "p_after_trend": p_after_trend,
            "market_mid": market_mid,
            "spread": spread,
        },
    )


def select_horizon_vol(snapshot: CryptoAssetSnapshot, horizon_hours: float) -> float:
    if horizon_hours <= 12:
        base = _blend(snapshot.realized_vol_1d, snapshot.realized_vol_3d, snapshot.realized_vol_7d)
    elif horizon_hours <= 72:
        base = _blend(snapshot.realized_vol_3d, snapshot.realized_vol_7d, snapshot.realized_vol_30d)
    elif horizon_hours <= 24 * 14:
        base = _blend(snapshot.realized_vol_7d, snapshot.realized_vol_30d, snapshot.realized_vol_90d)
    else:
        base = _blend(snapshot.realized_vol_30d, snapshot.realized_vol_90d)
    floor, cap = {
        "BTC": (0.25, 1.20),
        "ETH": (0.30, 1.50),
        "SOL": (0.45, 2.20),
    }.get(snapshot.asset.upper(), (0.25, 2.20))
    return clamp(base or floor, floor, cap)


def trend_adjustment(snapshot: CryptoAssetSnapshot, asset: str, market_type: str) -> float:
    score = 0.0
    if snapshot.momentum_24h is not None:
        score += clamp(snapshot.momentum_24h / 0.05, -1.0, 1.0)
    if snapshot.momentum_7d is not None:
        score += 0.5 * clamp(snapshot.momentum_7d / 0.12, -1.0, 1.0)
    if snapshot.funding_zscore is not None:
        score -= 0.25 * clamp(snapshot.funding_zscore / 2.5, -1.0, 1.0)
    adjustment = clamp(score * 0.015, -0.04, 0.04)
    if market_type in {"close_below", "hit_below"}:
        return -adjustment
    return adjustment


def _raw_probability(
    spec: CryptoMarketSpec,
    snapshot: CryptoAssetSnapshot,
    years: float,
    annualized_vol: float,
    horizon_hours: float,
    mc_paths: int,
    mc_seed: int,
) -> float:
    spot = float(snapshot.spot_mid)
    if spec.market_type == "close_above" and spec.threshold is not None:
        return close_above_probability(spot, float(spec.threshold), years, annualized_vol)
    if spec.market_type == "close_below" and spec.threshold is not None:
        return close_below_probability(spot, float(spec.threshold), years, annualized_vol)
    if spec.market_type == "range_close" and spec.lower_threshold is not None and spec.upper_threshold is not None:
        return range_close_probability(
            spot,
            float(spec.lower_threshold),
            float(spec.upper_threshold),
            years,
            annualized_vol,
        )
    if spec.market_type == "hit_above" and spec.threshold is not None:
        return touch_probability_mc(
            spot,
            float(spec.threshold),
            years,
            annualized_vol,
            "above",
            n_paths=mc_paths,
            n_steps=choose_mc_steps(horizon_hours),
            seed=mc_seed,
        )
    if spec.market_type == "hit_below" and spec.threshold is not None:
        return touch_probability_mc(
            spot,
            float(spec.threshold),
            years,
            annualized_vol,
            "below",
            n_paths=mc_paths,
            n_steps=choose_mc_steps(horizon_hours),
            seed=mc_seed,
        )
    return 0.5


def _blend(*values: float | None) -> float | None:
    usable = [float(value) for value in values if value is not None and value > 0]
    if not usable:
        return None
    return sum(usable) / len(usable)


def _data_quality(snapshot: CryptoAssetSnapshot) -> float:
    available = sum(
        value is not None
        for value in (
            snapshot.spot_mid,
            snapshot.realized_vol_7d,
            snapshot.realized_vol_30d,
            snapshot.realized_vol_90d,
        )
    )
    return clamp(0.5 + available * 0.125, 0.5, 1.0)
