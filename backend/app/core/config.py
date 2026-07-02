from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from decimal import Decimal
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator
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
    protocols: list[str] = Field(default_factory=lambda: ["POLYMARKET"])
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


class CryptoThresholdV1Section(BaseModel):
    enabled: bool = False

    @model_validator(mode="after")
    def force_disabled(self) -> "CryptoThresholdV1Section":
        self.enabled = False
        return self


class CryptoThresholdV2ParserSection(BaseModel):
    min_confidence: float = 0.85
    touch_min_confidence: float = 0.90
    block_on_ambiguity: bool = True


class CryptoThresholdV2MarketFiltersSection(BaseModel):
    min_quality_score: float = 70
    touch_min_quality_score: float = 75
    min_hours_to_close: float = 2
    max_days_to_close: float = 21
    block_extreme_prices: bool = True
    min_trade_price: float = 0.03
    max_trade_price: float = 0.97


class CryptoThresholdV2DataFreshnessSection(BaseModel):
    spot_seconds: int = 30
    orderbook_seconds: int = 15
    market_snapshot_seconds: int = 300
    asset_snapshot_cache_seconds: int = 20


class CryptoThresholdV2ProbabilitySection(BaseModel):
    model_family: str = "barrier_distance_v2"
    calibration_profile: str = "crypto_threshold_v2_default"
    uncertainty_penalty_multiplier: float = 1.0


class CryptoThresholdV2EdgeSection(BaseModel):
    min_exec_edge: float = 0.06
    min_stress_edge: float = 0.025
    touch_min_exec_edge: float = 0.08
    touch_min_stress_edge: float = 0.04
    max_spread_ct: float = 0.04
    uncertainty_penalty_multiplier: float = 1.0


class CryptoThresholdV2SizingSection(BaseModel):
    starting_equity: Decimal = Decimal("10000")
    min_notional: Decimal = Decimal("5")
    default_paper_notional_cap: Decimal = Decimal("100")
    kelly_fraction: float = 0.20
    max_position_pct: float = 0.01
    max_event_exposure_pct: float = 0.02
    max_asset_exposure_pct: float = 0.04
    max_asset_horizon_exposure_pct: float = 0.025
    max_category_exposure_pct: float = 0.15
    max_daily_new_risk_pct: float = 0.02
    depth_multiplier: float = 1.5


class CryptoThresholdV2ExitsSection(BaseModel):
    stale_data_exit_enabled: bool = True
    parser_block_exit_enabled: bool = True
    asset_data_unavailable_exit_enabled: bool = True


class CryptoThresholdV2PaperExecutionSection(BaseModel):
    use_bid_ask: bool = True
    auto_execute_signals: bool = True
    price_slippage_ct: Decimal = Decimal("0.0025")
    require_top_of_book_depth: bool = True


class CryptoThresholdV2RealExecutionSection(BaseModel):
    enabled: bool = False
    require_manual_approval: bool = True
    max_order_notional: Decimal = Decimal("10")
    order_ttl_seconds: int = 30
    time_in_force: Literal["FAK", "FOK", "GTC"] = "FAK"


class CryptoThresholdV2Section(BaseModel):
    enabled: bool = True
    legacy_v1_enabled: bool = False
    mode: Literal["paper_only", "observe_only", "auto_simulated"] = "paper_only"
    supported_assets: list[str] = Field(default_factory=lambda: ["BTC", "ETH", "SOL"])
    market_types: list[str] = Field(
        default_factory=lambda: ["close_above", "close_below", "hit_above", "hit_below", "range_close"]
    )
    venue_allowlist: list[str] = Field(default_factory=lambda: ["POLYMARKET"])
    parser: CryptoThresholdV2ParserSection = Field(default_factory=CryptoThresholdV2ParserSection)
    market_filters: CryptoThresholdV2MarketFiltersSection = Field(
        default_factory=CryptoThresholdV2MarketFiltersSection
    )
    data_freshness: CryptoThresholdV2DataFreshnessSection = Field(
        default_factory=CryptoThresholdV2DataFreshnessSection
    )
    probability: CryptoThresholdV2ProbabilitySection = Field(default_factory=CryptoThresholdV2ProbabilitySection)
    edge: CryptoThresholdV2EdgeSection = Field(default_factory=CryptoThresholdV2EdgeSection)
    sizing: CryptoThresholdV2SizingSection = Field(default_factory=CryptoThresholdV2SizingSection)
    exits: CryptoThresholdV2ExitsSection = Field(default_factory=CryptoThresholdV2ExitsSection)
    paper_execution: CryptoThresholdV2PaperExecutionSection = Field(
        default_factory=CryptoThresholdV2PaperExecutionSection
    )
    real_execution: CryptoThresholdV2RealExecutionSection = Field(
        default_factory=CryptoThresholdV2RealExecutionSection
    )


class MacroCalendarV1Section(BaseModel):
    enabled: bool = True
    mode: Literal["observe_and_manual_paper_only"] = "observe_and_manual_paper_only"


class StrategiesSection(BaseModel):
    crypto_threshold_v1: CryptoThresholdV1Section = Field(default_factory=CryptoThresholdV1Section)
    crypto_threshold_v2: CryptoThresholdV2Section = Field(default_factory=CryptoThresholdV2Section)
    macro_calendar_v1: MacroCalendarV1Section = Field(default_factory=MacroCalendarV1Section)


class RuntimeConfig(BaseModel):
    app: AppSection = Field(default_factory=AppSection)
    auth: AuthSection = Field(default_factory=AuthSection)
    codex: CodexSection = Field(default_factory=CodexSection)
    radar: RadarSection = Field(default_factory=RadarSection)
    paper: PaperSection = Field(default_factory=PaperSection)
    jobs: JobsSection = Field(default_factory=JobsSection)
    ingestion_tiers: IngestionTiersSection = Field(default_factory=IngestionTiersSection)
    strategies: StrategiesSection = Field(default_factory=StrategiesSection)


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_env: str = "dev"
    app_config_path: str = "../config/app.example.yaml"
    strategy_config_path: str | None = None
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


def _default_strategy_config_path(app_config_path: str) -> str:
    config_path = Path(app_config_path)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    strategy_path = config_path.parent / "strategy.yaml"
    if strategy_path.exists():
        return str(strategy_path)
    return str(config_path.parent / "strategy.example.yaml")


def _strategy_yaml_as_runtime_config(strategy_yaml: dict[str, Any]) -> dict[str, Any]:
    if not strategy_yaml:
        return {}
    if "strategies" in strategy_yaml:
        return strategy_yaml
    return {"strategies": strategy_yaml}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    env = EnvSettings()
    if env.app_env == "prod" and len(env.jwt_secret) < 32:
        raise ValueError("JWT_SECRET must be at least 32 characters in prod")
    defaults = RuntimeConfig().model_dump()
    yaml_config = _load_yaml_config(env.app_config_path)
    strategy_config_path = env.strategy_config_path or _default_strategy_config_path(env.app_config_path)
    strategy_config = _strategy_yaml_as_runtime_config(_load_yaml_config(strategy_config_path))
    runtime = RuntimeConfig.model_validate(_deep_merge(_deep_merge(defaults, strategy_config), yaml_config))
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
