from __future__ import annotations


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def default_calibrate(p_raw: float, data_quality: float, market_type: str) -> tuple[float, float]:
    base_reliability = {
        "close_above": 0.70,
        "close_below": 0.70,
        "range_close": 0.60,
        "hit_above": 0.55,
        "hit_below": 0.55,
    }[market_type]
    reliability = base_reliability * clamp(data_quality, 0.5, 1.0)
    p_calibrated = 0.5 + reliability * (p_raw - 0.5)
    uncertainty_penalty = {
        "close_above": 0.015,
        "close_below": 0.015,
        "range_close": 0.025,
        "hit_above": 0.035,
        "hit_below": 0.035,
    }[market_type]
    return clamp(p_calibrated, 0.0, 1.0), uncertainty_penalty


def blend_with_market_prior(
    p_model: float,
    p_market_mid: float | None,
    spread: float | None,
    model_confidence: float,
) -> float:
    if p_market_mid is None or spread is None:
        return clamp(p_model, 0.0, 1.0)
    market_weight = clamp(0.25 * (1.0 - spread / 0.10), 0.05, 0.25)
    reliability = clamp(model_confidence, 0.35, 0.85)
    p_shrunk = 0.5 + reliability * (p_model - 0.5)
    return clamp((1 - market_weight) * p_shrunk + market_weight * p_market_mid, 0.0, 1.0)
