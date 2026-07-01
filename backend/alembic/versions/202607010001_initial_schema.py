"""initial schema

Revision ID: 202607010001
Revises:
Create Date: 2026-07-01
"""

from __future__ import annotations

from alembic import op

from app.db.session import Base
import app.db.models  # noqa: F401

revision = "202607010001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

