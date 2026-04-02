"""Enforce one open time entry per employee

Revision ID: 20260402_000007
Revises: 20260402_000006
Create Date: 2026-04-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260402_000007"
down_revision = "20260402_000006"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    indexes = inspector.get_indexes(table_name)
    return any(index.get("name") == index_name for index in indexes)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "time_entries"
    index_name = "uq_time_entries_open_per_employee"

    if not _table_exists(inspector, table_name):
        return

    open_rows = bind.execute(
        sa.text(
            "SELECT id, employee_id, clock_in_at "
            "FROM time_entries "
            "WHERE clock_out_at IS NULL "
            "ORDER BY employee_id, clock_in_at DESC, id DESC"
        )
    ).all()
    seen_employee_ids: set[int] = set()
    duplicate_open_ids: list[int] = []
    for row in open_rows:
        employee_id = int(row.employee_id)
        if employee_id in seen_employee_ids:
            duplicate_open_ids.append(int(row.id))
            continue
        seen_employee_ids.add(employee_id)

    if duplicate_open_ids:
        time_entries_table = sa.table(
            "time_entries",
            sa.column("id", sa.Integer()),
            sa.column("clock_in_at", sa.DateTime()),
            sa.column("clock_out_at", sa.DateTime()),
            sa.column("clock_out_source", sa.String()),
        )
        for entry_id in duplicate_open_ids:
            entry = bind.execute(
                sa.select(time_entries_table.c.clock_in_at).where(time_entries_table.c.id == entry_id)
            ).first()
            if not entry:
                continue
            bind.execute(
                sa.update(time_entries_table)
                .where(time_entries_table.c.id == entry_id)
                .values(clock_out_at=entry.clock_in_at, clock_out_source="system_dedupe")
            )

    inspector = sa.inspect(bind)
    if _index_exists(inspector, table_name, index_name):
        return

    dialect_name = bind.dialect.name
    if dialect_name == "postgresql":
        op.create_index(index_name, table_name, ["employee_id"], unique=True, postgresql_where=sa.text("clock_out_at IS NULL"))
    elif dialect_name == "sqlite":
        op.create_index(index_name, table_name, ["employee_id"], unique=True, sqlite_where=sa.text("clock_out_at IS NULL"))
    else:
        op.create_index(index_name, table_name, ["employee_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "time_entries"
    index_name = "uq_time_entries_open_per_employee"

    if not _table_exists(inspector, table_name):
        return
    if _index_exists(inspector, table_name, index_name):
        op.drop_index(index_name, table_name=table_name)
