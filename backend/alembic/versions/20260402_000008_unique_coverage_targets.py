"""Enforce unique coverage targets by daypart and optional role

Revision ID: 20260402_000008
Revises: 20260402_000007
Create Date: 2026-04-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260402_000008"
down_revision = "20260402_000007"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    indexes = inspector.get_indexes(table_name)
    return any(index.get("name") == index_name for index in indexes)


def _dedupe_coverage_targets(bind: sa.Connection) -> None:
    rows = bind.execute(
        sa.text(
            "SELECT id, organization_id, weekday, daypart, role_label "
            "FROM schedule_coverage_targets "
            "ORDER BY organization_id, weekday, daypart, role_label, created_at DESC, id DESC"
        )
    ).all()
    seen_keys: set[tuple[int, int, str, str | None]] = set()
    duplicate_ids: list[int] = []
    for row in rows:
        role_value = None if row.role_label is None else str(row.role_label)
        key = (int(row.organization_id), int(row.weekday), str(row.daypart), role_value)
        if key in seen_keys:
            duplicate_ids.append(int(row.id))
            continue
        seen_keys.add(key)

    if duplicate_ids:
        target_table = sa.table("schedule_coverage_targets", sa.column("id", sa.Integer()))
        bind.execute(sa.delete(target_table).where(target_table.c.id.in_(duplicate_ids)))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "schedule_coverage_targets"
    index_null = "uq_coverage_target_org_weekday_daypart_null_role"
    index_role = "uq_coverage_target_org_weekday_daypart_role"

    if not _table_exists(inspector, table_name):
        return

    _dedupe_coverage_targets(bind)
    inspector = sa.inspect(bind)

    if bind.dialect.name == "postgresql":
        if not _index_exists(inspector, table_name, index_null):
            op.create_index(index_null, table_name, ["organization_id", "weekday", "daypart"], unique=True, postgresql_where=sa.text("role_label IS NULL"))
        inspector = sa.inspect(bind)
        if not _index_exists(inspector, table_name, index_role):
            op.create_index(
                index_role,
                table_name,
                ["organization_id", "weekday", "daypart", "role_label"],
                unique=True,
                postgresql_where=sa.text("role_label IS NOT NULL"),
            )
    elif bind.dialect.name == "sqlite":
        if not _index_exists(inspector, table_name, index_null):
            op.create_index(index_null, table_name, ["organization_id", "weekday", "daypart"], unique=True, sqlite_where=sa.text("role_label IS NULL"))
        inspector = sa.inspect(bind)
        if not _index_exists(inspector, table_name, index_role):
            op.create_index(
                index_role,
                table_name,
                ["organization_id", "weekday", "daypart", "role_label"],
                unique=True,
                sqlite_where=sa.text("role_label IS NOT NULL"),
            )
    else:
        # Fallback for unsupported dialects: no partial unique index support in this migration.
        return


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "schedule_coverage_targets"
    index_null = "uq_coverage_target_org_weekday_daypart_null_role"
    index_role = "uq_coverage_target_org_weekday_daypart_role"

    if not _table_exists(inspector, table_name):
        return
    if _index_exists(inspector, table_name, index_role):
        op.drop_index(index_role, table_name=table_name)
    inspector = sa.inspect(bind)
    if _index_exists(inspector, table_name, index_null):
        op.drop_index(index_null, table_name=table_name)
