from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.core.config import get_settings
from app.db.models import PredictionEvent, PredictionMarket


def default_watchlist_path() -> Path:
    return Path(get_settings().app_config_path).with_name("watchlist.yaml")


def load_watchlist(watchlist_path: str | Path | None) -> dict[str, list[str]]:
    if watchlist_path is None:
        return {"event_ids": [], "market_ids": [], "keywords": []}
    path = Path(watchlist_path)
    if not path.exists():
        return {"event_ids": [], "market_ids": [], "keywords": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_watchlist = data.get("watchlist") if isinstance(data, dict) else {}
    if not isinstance(raw_watchlist, dict):
        raw_watchlist = {}
    return {
        "event_ids": _string_list(raw_watchlist.get("event_ids")),
        "market_ids": _string_list(raw_watchlist.get("market_ids")),
        "keywords": _string_list(raw_watchlist.get("keywords")),
    }


def market_matches_watchlist(
    event: PredictionEvent,
    market: PredictionMarket,
    watchlist: dict[str, list[str]],
) -> bool:
    if event.external_event_id in watchlist["event_ids"]:
        return True
    if market.external_market_id in watchlist["market_ids"]:
        return True
    question = f"{event.question} {market.question}".lower()
    return any(keyword.lower() in question for keyword in watchlist["keywords"])


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
