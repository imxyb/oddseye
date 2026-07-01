from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.session import Base


def uuid_str() -> str:
    return str(uuid4())


JSONType = JSON


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    supports_execution: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PredictionCategory(Base):
    __tablename__ = "prediction_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    parent_slug: Mapped[str | None] = mapped_column(String(128))
    raw_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PredictionEvent(Base):
    __tablename__ = "prediction_events"
    __table_args__ = (UniqueConstraint("venue_id", "external_event_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    venue_id: Mapped[str] = mapped_column(ForeignKey("venues.id"), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(256), nullable=False)
    protocol: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(512))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    categories: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    venue_url: Mapped[str | None] = mapped_column(Text)
    image_thumb_url: Mapped[str | None] = mapped_column(Text)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolves_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    market_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    venue: Mapped[Venue] = relationship()


class PredictionMarket(Base):
    __tablename__ = "prediction_markets"
    __table_args__ = (UniqueConstraint("venue_id", "external_market_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    event_id: Mapped[str] = mapped_column(ForeignKey("prediction_events.id"), nullable=False)
    venue_id: Mapped[str] = mapped_column(ForeignKey("venues.id"), nullable=False)
    external_market_id: Mapped[str] = mapped_column(String(256), nullable=False)
    protocol: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome_type: Mapped[str] = mapped_column(String(32), default="binary", nullable=False)
    image_thumb_url: Mapped[str | None] = mapped_column(Text)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolves_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_source: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped[PredictionEvent] = relationship()
    venue: Mapped[Venue] = relationship()


class MarketOutcome(Base):
    __tablename__ = "market_outcomes"
    __table_args__ = (UniqueConstraint("market_id", "outcome_index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    market_id: Mapped[str] = mapped_column(ForeignKey("prediction_markets.id"), nullable=False)
    outcome_index: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    external_token_id: Mapped[str | None] = mapped_column(String(256))
    raw_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (
        Index("idx_market_snapshots_market_ts", "market_id", "ts"),
        Index("idx_market_snapshots_ts", "ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("prediction_markets.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome0_label: Mapped[str | None] = mapped_column(String(256))
    outcome0_best_ask: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    outcome0_best_bid: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    outcome0_spread: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    outcome0_last_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    outcome0_liquidity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    outcome0_volume_usd_24h: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    outcome1_label: Mapped[str | None] = mapped_column(String(256))
    outcome1_best_ask: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    outcome1_best_bid: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    outcome1_spread: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    outcome1_last_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    outcome1_liquidity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    outcome1_volume_usd_24h: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    liquidity_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    open_interest_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    volume_usd_24h: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    trades_24h: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    competitive_score_24h: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    trending_score_24h: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    market_quality_score: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    raw_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)


class ModelSignal(Base):
    __tablename__ = "model_signals"
    __table_args__ = (
        Index("idx_model_signals_ts", "ts"),
        Index("idx_model_signals_market_ts", "market_id", "ts"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    market_id: Mapped[str] = mapped_column(ForeignKey("prediction_markets.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    strategy_code: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str | None] = mapped_column(String(16))
    model_probability: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    executable_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    edge: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    suggested_notional: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    market_quality_score: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    reason_codes: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    risk_flags: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)


class PaperAccount(Base):
    __tablename__ = "paper_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    starting_cash: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), default="USDC", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaperOrder(Base):
    __tablename__ = "paper_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    account_id: Mapped[str] = mapped_column(ForeignKey("paper_accounts.id"), nullable=False)
    market_id: Mapped[str] = mapped_column(ForeignKey("prediction_markets.id"), nullable=False)
    signal_id: Mapped[str | None] = mapped_column(ForeignKey("model_signals.id"))
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    outcome_index: Mapped[int] = mapped_column(Integer, nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), default="limit", nullable=False)
    limit_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaperFill(Base):
    __tablename__ = "paper_fills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    order_id: Mapped[str] = mapped_column(ForeignKey("paper_orders.id"), nullable=False)
    account_id: Mapped[str] = mapped_column(ForeignKey("paper_accounts.id"), nullable=False)
    market_id: Mapped[str] = mapped_column(ForeignKey("prediction_markets.id"), nullable=False)
    outcome_index: Mapped[int] = mapped_column(Integer, nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    notional: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0, nullable=False)
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("market_snapshots.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaperPosition(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (UniqueConstraint("account_id", "market_id", "outcome_index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    account_id: Mapped[str] = mapped_column(ForeignKey("paper_accounts.id"), nullable=False)
    market_id: Mapped[str] = mapped_column(ForeignKey("prediction_markets.id"), nullable=False)
    outcome_index: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    avg_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    mark_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0, nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketResolution(Base):
    __tablename__ = "market_resolutions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    market_id: Mapped[str] = mapped_column(ForeignKey("prediction_markets.id"), nullable=False)
    resolved_outcome_index: Mapped[int | None] = mapped_column(Integer)
    resolved_label: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    job_name: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    records_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    codex_requests_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ApiUsageLedger(Base):
    __tablename__ = "api_usage_ledger"
    __table_args__ = (Index("idx_api_usage_ledger_ts", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    job_run_id: Mapped[str | None] = mapped_column(ForeignKey("job_runs.id"))
    metadata_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
