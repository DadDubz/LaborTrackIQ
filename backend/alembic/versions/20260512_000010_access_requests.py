"""Create access requests table for public lead capture

Revision ID: 20260512_000010
Revises: 20260402_000009
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260512_000010"
down_revision = "20260402_000009"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "access_requests"):
        return

    op.create_table(
        "access_requests",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("restaurant_name", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("locations", sa.Integer(), nullable=True),
        sa.Column("current_tools", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="website"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_access_requests_id", "access_requests", ["id"], unique=False)
    op.create_index("ix_access_requests_email", "access_requests", ["email"], unique=False)
    op.create_index("ix_access_requests_created_at", "access_requests", ["created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "access_requests"):
        return

    op.drop_index("ix_access_requests_created_at", table_name="access_requests")
    op.drop_index("ix_access_requests_email", table_name="access_requests")
    op.drop_index("ix_access_requests_id", table_name="access_requests")
    op.drop_table("access_requests")
