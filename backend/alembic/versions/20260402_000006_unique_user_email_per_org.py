"""Enforce unique user email per organization

Revision ID: 20260402_000006
Revises: 20260402_000005
Create Date: 2026-04-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260402_000006"
down_revision = "20260402_000005"
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
    table_name = "users"
    constraint_name = "uq_users_org_email"

    if not _table_exists(inspector, table_name):
        return

    rows = bind.execute(
        sa.text(
            "SELECT id, organization_id, email "
            "FROM users "
            "WHERE email IS NOT NULL "
            "ORDER BY organization_id, email, is_active DESC, id DESC"
        )
    ).all()
    seen_keys: set[tuple[int, str]] = set()
    duplicate_ids: list[int] = []
    for row in rows:
        key = (int(row.organization_id), str(row.email))
        if key in seen_keys:
            duplicate_ids.append(int(row.id))
            continue
        seen_keys.add(key)

    if duplicate_ids:
        users_table = sa.table("users", sa.column("id", sa.Integer()), sa.column("email", sa.String()))
        bind.execute(sa.update(users_table).where(users_table.c.id.in_(duplicate_ids)).values(email=None))

    inspector = sa.inspect(bind)
    if not _unique_constraint_exists(inspector, table_name, constraint_name):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_unique_constraint(constraint_name, ["organization_id", "email"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "users"
    constraint_name = "uq_users_org_email"

    if not _table_exists(inspector, table_name):
        return
    if _unique_constraint_exists(inspector, table_name, constraint_name):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(constraint_name, type_="unique")
