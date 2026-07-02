from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSection(BaseModel):
    name: str = "prediction-radar"
    timezone: str = "Asia/Singapore"
    base_currency: str = "USDC"


class AuthUser(BaseModel):
    username: str
    password_hash: str
    role: str = "admin"


class AuthSection(BaseModel):
    users: list[AuthUser] = Field(default_factory=list)
    token_expires_days: int = 7


class CodexSection(BaseModel):
    endpoint: str = "https://graph.codex.io/graphql"
    timeout_seconds: int = 20
    max_retries: int = 3
    usage_tracking_enabled: bool = True
    usage_policy: Literal["advisory_only"] = "advisory_only"
    global_monthly_reference_budget: int = 1_000_000
    external_daily_usage_estimate: int = 12_000
    radar_daily_target_requests: int = 2_000
    radar_daily_review_threshold: int = 5_000
    radar_monthly_review_threshold: int = 150_000
    fetch_profile: Literal["light", "normal", "aggressive"] = "light"


class RadarSection(BaseModel):
    enabled_categories: list[str] = Field(default_factory=lambda: ["crypto", "economics", "finance"])
    protocols: list[str] = Field(default_factory=lambda: ["POLYMARKET", "KALSHI"])
    min_liquidity_usd: float = 1_000
    min_volume_usd_24h: float = 500
    max_spread_ct: float = 0.08
    max_markets_per_ingest: int = 300


class PaperSection(BaseModel):
    starting_cash: float = 10_000
    currency: str = "USDC"
    fee_bps: int = 0
    slippage_bps: int = 25
    max_position_pct: float = 0.03
    max_market_risk_pct: float = 0.05
    max_daily_loss_pct: float = 0.03
    max_category_exposure_pct: float = 0.15
    allow_short: bool = False


class JobsSection(BaseModel):
    categories_refresh_cron: str = "0 3 * * *"
    market_discovery_seconds: int = 1_800
    hot_market_snapshot_seconds: int = 300
    warm_market_snapshot_seconds: int = 1_800
    cold_market_snapshot_seconds: int = 21_600
    signal_seconds: int = 300
    paper_mark_seconds: int = 300
    resolution_poll_seconds: int = 7_200


class IngestionTiersSection(BaseModel):
    hot_watchlist_max_markets: int = 30
    warm_pool_max_markets: int = 120
    cold_pool_max_markets: int = 500
    bars_fetch_mode: Literal["on_demand"] = "on_demand"
    manual_refresh_enabled: bool = True


class RuntimeConfig(BaseModel):
    app: AppSection = Field(default_factory=AppSection)
    auth: AuthSection = Field(default_factory=AuthSection)
    codex: CodexSection = Field(default_factory=CodexSection)
    radar: RadarSection = Field(default_factory=RadarSection)
    paper: PaperSection = Field(default_factory=PaperSection)
    jobs: JobsSection = Field(default_factory=JobsSection)
    ingestion_tiers: IngestionTiersSection = Field(default_factory=IngestionTiersSection)


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_env: str = "dev"
    app_config_path: str = "../config/app.example.yaml"
    database_url: str = "sqlite+aiosqlite:///./prediction_radar.db"
    redis_url: str | None = "redis://localhost:6379/0"
    codex_api_key: str = ""
    jwt_secret: str = "change-me-change-me-change-me-change-me"
    jwt_expires_days: int = 7
    log_level: str = "INFO"


class Settings(BaseModel):
    app_env: str
    app_config_path: str
    database_url: str
    redis_url: str | None
    codex_api_key: str
    jwt_secret: str
    jwt_expires_days: int
    log_level: str
    config: RuntimeConfig


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml_config(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    env = EnvSettings()
    if env.app_env == "prod" and len(env.jwt_secret) < 32:
        raise ValueError("JWT_SECRET must be at least 32 characters in prod")
    defaults = RuntimeConfig().model_dump()
    yaml_config = _load_yaml_config(env.app_config_path)
    runtime = RuntimeConfig.model_validate(_deep_merge(defaults, yaml_config))
    return Settings(
        app_env=env.app_env,
        app_config_path=env.app_config_path,
        database_url=env.database_url,
        redis_url=env.redis_url,
        codex_api_key=env.codex_api_key,
        jwt_secret=env.jwt_secret,
        jwt_expires_days=env.jwt_expires_days,
        log_level=env.log_level,
        config=runtime,
    )
