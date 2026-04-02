"""Enforce one pending shift-change request per shift/requester

Revision ID: 20260402_000009
Revises: 20260402_000008
Create Date: 2026-04-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260402_000009"
down_revision = "20260402_000008"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    indexes = inspector.get_indexes(table_name)
    return any(index.get("name") == index_name for index in indexes)


def _dedupe_pending_shift_change_requests(bind: sa.Connection) -> None:
    rows = bind.execute(
        sa.text(
            "SELECT id, shift_id, requester_employee_id "
            "FROM shift_change_requests "
            "WHERE status = 'PENDING' "
            "ORDER BY shift_id, requester_employee_id, created_at DESC, id DESC"
        )
    ).all()
    seen_keys: set[tuple[int, int]] = set()
    duplicate_ids: list[int] = []
    for row in rows:
        key = (int(row.shift_id), int(row.requester_employee_id))
        if key in seen_keys:
            duplicate_ids.append(int(row.id))
            continue
        seen_keys.add(key)

    if duplicate_ids:
        requests_table = sa.table(
            "shift_change_requests",
            sa.column("id", sa.Integer()),
            sa.column("status", sa.String()),
            sa.column("manager_response", sa.Text()),
            sa.column("reviewed_at", sa.DateTime()),
        )
        bind.execute(
            sa.update(requests_table)
            .where(requests_table.c.id.in_(duplicate_ids))
            .values(
                status="DENIED",
                manager_response="Duplicate pending request removed during data integrity cleanup.",
                reviewed_at=sa.func.now(),
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "shift_change_requests"
    index_name = "uq_shift_change_pending_per_shift_requester"

    if not _table_exists(inspector, table_name):
        return

    _dedupe_pending_shift_change_requests(bind)
    inspector = sa.inspect(bind)
    if _index_exists(inspector, table_name, index_name):
        return

    if bind.dialect.name == "postgresql":
        op.create_index(index_name, table_name, ["shift_id", "requester_employee_id"], unique=True, postgresql_where=sa.text("status = 'PENDING'"))
    elif bind.dialect.name == "sqlite":
        op.create_index(index_name, table_name, ["shift_id", "requester_employee_id"], unique=True, sqlite_where=sa.text("status = 'PENDING'"))
    else:
        return


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "shift_change_requests"
    index_name = "uq_shift_change_pending_per_shift_requester"

    if not _table_exists(inspector, table_name):
        return
    if _index_exists(inspector, table_name, index_name):
        op.drop_index(index_name, table_name=table_name)
