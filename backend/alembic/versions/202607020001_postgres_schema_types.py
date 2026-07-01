"""align postgres schema types with V1 document

Revision ID: 202607020001
Revises: 202607010001
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "202607020001"
down_revision = "202607010001"
branch_labels = None
depends_on = None


UUID_COLUMNS = {
    "venues": ["id"],
    "prediction_categories": ["id"],
    "prediction_events": ["id", "venue_id"],
    "prediction_markets": ["id", "event_id", "venue_id"],
    "market_outcomes": ["id", "market_id"],
    "market_snapshots": ["market_id"],
    "model_signals": ["id", "market_id"],
    "paper_accounts": ["id"],
    "paper_orders": ["id", "account_id", "market_id", "signal_id"],
    "paper_fills": ["id", "order_id", "account_id", "market_id"],
    "paper_positions": ["id", "account_id", "market_id"],
    "market_resolutions": ["id", "market_id"],
    "job_runs": ["id"],
    "api_usage_ledger": ["job_run_id"],
}

JSONB_COLUMNS = {
    "prediction_categories": ["raw_json"],
    "prediction_events": ["raw_json"],
    "prediction_markets": ["raw_json"],
    "market_outcomes": ["raw_json"],
    "market_snapshots": ["raw_json"],
    "model_signals": ["raw_json"],
    "market_resolutions": ["raw_json"],
    "api_usage_ledger": ["metadata_json"],
}

TEXT_ARRAY_COLUMNS = {
    "prediction_events": ["categories"],
    "model_signals": ["reason_codes", "risk_flags"],
}

FOREIGN_KEYS = [
    ("prediction_events", "prediction_events_venue_id_fkey", "venue_id", "venues"),
    ("prediction_markets", "prediction_markets_event_id_fkey", "event_id", "prediction_events"),
    ("prediction_markets", "prediction_markets_venue_id_fkey", "venue_id", "venues"),
    ("market_outcomes", "market_outcomes_market_id_fkey", "market_id", "prediction_markets"),
    ("market_snapshots", "market_snapshots_market_id_fkey", "market_id", "prediction_markets"),
    ("model_signals", "model_signals_market_id_fkey", "market_id", "prediction_markets"),
    ("paper_orders", "paper_orders_account_id_fkey", "account_id", "paper_accounts"),
    ("paper_orders", "paper_orders_market_id_fkey", "market_id", "prediction_markets"),
    ("paper_orders", "paper_orders_signal_id_fkey", "signal_id", "model_signals"),
    ("paper_fills", "paper_fills_order_id_fkey", "order_id", "paper_orders"),
    ("paper_fills", "paper_fills_account_id_fkey", "account_id", "paper_accounts"),
    ("paper_fills", "paper_fills_market_id_fkey", "market_id", "prediction_markets"),
    ("paper_fills", "paper_fills_snapshot_id_fkey", "snapshot_id", "market_snapshots"),
    ("paper_positions", "paper_positions_account_id_fkey", "account_id", "paper_accounts"),
    ("paper_positions", "paper_positions_market_id_fkey", "market_id", "prediction_markets"),
    ("market_resolutions", "market_resolutions_market_id_fkey", "market_id", "prediction_markets"),
    ("api_usage_ledger", "api_usage_ledger_job_run_id_fkey", "job_run_id", "job_runs"),
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    _drop_foreign_keys()
    _alter_uuid_columns()
    _alter_bigint_columns()
    _alter_jsonb_columns()
    _alter_text_array_columns()
    _create_foreign_keys()


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    _drop_foreign_keys()
    _alter_text_array_columns_to_jsonb()
    _create_foreign_keys()


def _drop_foreign_keys() -> None:
    for table, constraint, _column, _target in FOREIGN_KEYS:
        op.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{constraint}"')


def _create_foreign_keys() -> None:
    for table, constraint, column, target in FOREIGN_KEYS:
        op.execute(
            f"""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = '{constraint}'
                  AND conrelid = '{table}'::regclass
              ) THEN
                ALTER TABLE "{table}"
                ADD CONSTRAINT "{constraint}"
                FOREIGN KEY ("{column}") REFERENCES "{target}" (id);
              END IF;
            END $$;
            """
        )


def _alter_uuid_columns() -> None:
    for table, columns in UUID_COLUMNS.items():
        for column in columns:
            if _column_udt_name(table, column) == "uuid":
                continue
            op.execute(
                f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE uuid '
                f'USING NULLIF("{column}", \'\')::uuid'
            )


def _alter_bigint_columns() -> None:
    if _column_udt_name("market_snapshots", "id") == "int8":
        return
    op.execute('ALTER TABLE "market_snapshots" ALTER COLUMN "id" TYPE bigint')


def _alter_jsonb_columns() -> None:
    for table, columns in JSONB_COLUMNS.items():
        for column in columns:
            if _column_udt_name(table, column) == "jsonb":
                continue
            op.execute(
                f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE jsonb '
                f'USING COALESCE("{column}"::jsonb, \'{{}}\'::jsonb)'
            )


def _alter_text_array_columns() -> None:
    _create_json_array_helpers()
    try:
        for table, columns in TEXT_ARRAY_COLUMNS.items():
            for column in columns:
                udt_name = _column_udt_name(table, column)
                if udt_name == "_text":
                    continue
                if udt_name == "jsonb":
                    converter = "_oddseye_jsonb_to_text_array"
                else:
                    converter = "_oddseye_json_to_text_array"
                op.execute(
                    f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE text[] '
                    f'USING {converter}("{column}")'
                )
    finally:
        op.execute("DROP FUNCTION IF EXISTS _oddseye_json_to_text_array(json)")
        op.execute("DROP FUNCTION IF EXISTS _oddseye_jsonb_to_text_array(jsonb)")


def _alter_text_array_columns_to_jsonb() -> None:
    for table, columns in TEXT_ARRAY_COLUMNS.items():
        for column in columns:
            if _column_udt_name(table, column) != "_text":
                continue
            op.execute(
                f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE jsonb '
                f'USING to_jsonb(COALESCE("{column}", ARRAY[]::text[]))'
            )


def _create_json_array_helpers() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION _oddseye_json_to_text_array(value json)
        RETURNS text[]
        LANGUAGE sql
        IMMUTABLE
        AS $$
          SELECT COALESCE(array_agg(item), ARRAY[]::text[])
          FROM json_array_elements_text(COALESCE(value, '[]'::json)) AS item
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION _oddseye_jsonb_to_text_array(value jsonb)
        RETURNS text[]
        LANGUAGE sql
        IMMUTABLE
        AS $$
          SELECT COALESCE(array_agg(item), ARRAY[]::text[])
          FROM jsonb_array_elements_text(COALESCE(value, '[]'::jsonb)) AS item
        $$;
        """
    )


def _column_udt_name(table: str, column: str) -> str | None:
    row = op.get_bind().execute(
        text(
            """
            SELECT udt_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = :table
              AND column_name = :column
            """
        ),
        {"table": table, "column": column},
    ).first()
    return None if row is None else row[0]
