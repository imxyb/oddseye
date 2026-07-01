from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.db.models import MarketSnapshot, ModelSignal, PredictionEvent, PredictionMarket


def _postgres_create_table(table) -> str:
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))


def test_prediction_tables_compile_to_documented_postgres_types() -> None:
    event_ddl = _postgres_create_table(PredictionEvent.__table__)
    market_ddl = _postgres_create_table(PredictionMarket.__table__)

    assert "id UUID NOT NULL" in event_ddl
    assert "venue_id UUID NOT NULL" in event_ddl
    assert "categories TEXT[]" in event_ddl
    assert "raw_json JSONB NOT NULL" in event_ddl
    assert "id UUID NOT NULL" in market_ddl
    assert "raw_json JSONB NOT NULL" in market_ddl


def test_signal_and_snapshot_tables_compile_to_documented_postgres_types() -> None:
    snapshot_ddl = _postgres_create_table(MarketSnapshot.__table__)
    signal_ddl = _postgres_create_table(ModelSignal.__table__)

    assert "id BIGSERIAL NOT NULL" in snapshot_ddl
    assert "market_id UUID NOT NULL" in snapshot_ddl
    assert "raw_json JSONB NOT NULL" in snapshot_ddl
    assert "id UUID NOT NULL" in signal_ddl
    assert "market_id UUID NOT NULL" in signal_ddl
    assert "reason_codes TEXT[] NOT NULL" in signal_ddl
    assert "risk_flags TEXT[] NOT NULL" in signal_ddl
    assert "raw_json JSONB NOT NULL" in signal_ddl
