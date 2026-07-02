"""add api usage provider timestamp index

Revision ID: 202607020002
Revises: 202607020001
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op

revision = "202607020002"
down_revision = "202607020001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_api_usage_ledger_provider_ts",
        "api_usage_ledger",
        ["provider", "ts"],
    )


def downgrade() -> None:
    op.drop_index("idx_api_usage_ledger_provider_ts", table_name="api_usage_ledger")
