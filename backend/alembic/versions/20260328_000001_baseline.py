"""Baseline schema migration

Revision ID: 20260328_000001
Revises:
Create Date: 2026-03-28
"""

from __future__ import annotations

from alembic import op

from app.db.session import Base
from app import models  # noqa: F401


revision = "20260328_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
