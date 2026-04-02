"""Enforce unique integration provider per organization

Revision ID: 20260402_000003
Revises: 20260402_000002
Create Date: 2026-04-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260402_000003"
down_revision = "20260402_000002"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _unique_constraint_exists(inspector: sa.Inspector, table_name: str, constraint_name: str) -> bool:
    constraints = inspector.get_unique_constraints(table_name)
    return any(constraint.get("name") == constraint_name for constraint in constraints)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "integration_connections"
    constraint_name = "uq_integration_connections_org_provider"

    if not _table_exists(inspector, table_name):
        return

    rows = bind.execute(
        sa.text(
            "SELECT id, organization_id, provider "
            "FROM integration_connections "
            "ORDER BY organization_id, provider, id DESC"
        )
    ).all()
    seen_keys: set[tuple[int, str]] = set()
    duplicate_ids: list[int] = []
    for row in rows:
        key = (int(row.organization_id), str(row.provider))
        if key in seen_keys:
            duplicate_ids.append(int(row.id))
            continue
        seen_keys.add(key)

    if duplicate_ids:
        integration_table = sa.table("integration_connections", sa.column("id", sa.Integer()))
        bind.execute(sa.delete(integration_table).where(integration_table.c.id.in_(duplicate_ids)))

    inspector = sa.inspect(bind)
    if not _unique_constraint_exists(inspector, table_name, constraint_name):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_unique_constraint(constraint_name, ["organization_id", "provider"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "integration_connections"
    constraint_name = "uq_integration_connections_org_provider"

    if not _table_exists(inspector, table_name):
        return
    if _unique_constraint_exists(inspector, table_name, constraint_name):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(constraint_name, type_="unique")
