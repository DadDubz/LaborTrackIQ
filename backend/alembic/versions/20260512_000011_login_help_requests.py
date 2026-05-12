"""Create login help requests table for credential recovery support

Revision ID: 20260512_000011
Revises: 20260512_000010
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260512_000011"
down_revision = "20260512_000010"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "login_help_requests"):
        return

    op.create_table(
        "login_help_requests",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organization_reference", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="website"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_login_help_requests_id", "login_help_requests", ["id"], unique=False)
    op.create_index("ix_login_help_requests_email", "login_help_requests", ["email"], unique=False)
    op.create_index("ix_login_help_requests_created_at", "login_help_requests", ["created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "login_help_requests"):
        return

    op.drop_index("ix_login_help_requests_created_at", table_name="login_help_requests")
    op.drop_index("ix_login_help_requests_email", table_name="login_help_requests")
    op.drop_index("ix_login_help_requests_id", table_name="login_help_requests")
    op.drop_table("login_help_requests")
