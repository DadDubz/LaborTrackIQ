"""Backfill schema additions after baseline release

Revision ID: 20260402_000002
Revises: 20260328_000001
Create Date: 2026-04-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260402_000002"
down_revision = "20260328_000001"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "schedule_shifts"):
        if not _column_exists(inspector, "schedule_shifts", "is_published"):
            op.add_column("schedule_shifts", sa.Column("is_published", sa.Boolean(), nullable=True, server_default=sa.false()))
        if not _column_exists(inspector, "schedule_shifts", "published_at"):
            op.add_column("schedule_shifts", sa.Column("published_at", sa.DateTime(), nullable=True))
        if not _column_exists(inspector, "schedule_shifts", "published_by_name"):
            op.add_column("schedule_shifts", sa.Column("published_by_name", sa.String(length=180), nullable=True))

    if _table_exists(inspector, "schedule_publication_events") and not _column_exists(
        inspector, "schedule_publication_events", "comment"
    ):
        op.add_column("schedule_publication_events", sa.Column("comment", sa.Text(), nullable=True))

    if _table_exists(inspector, "schedule_coverage_targets") and not _column_exists(
        inspector, "schedule_coverage_targets", "role_label"
    ):
        op.add_column("schedule_coverage_targets", sa.Column("role_label", sa.String(length=120), nullable=True))

    if _table_exists(inspector, "employee_profiles"):
        if not _column_exists(inspector, "employee_profiles", "preferred_weekly_hours"):
            op.add_column("employee_profiles", sa.Column("preferred_weekly_hours", sa.Integer(), nullable=True))
        if not _column_exists(inspector, "employee_profiles", "preferred_shift_notes"):
            op.add_column("employee_profiles", sa.Column("preferred_shift_notes", sa.Text(), nullable=True))
        if not _column_exists(inspector, "employee_profiles", "pin_hash"):
            op.add_column("employee_profiles", sa.Column("pin_hash", sa.String(length=255), nullable=True))

    if _table_exists(inspector, "employee_availability_requests"):
        if not _column_exists(inspector, "employee_availability_requests", "start_date"):
            op.add_column("employee_availability_requests", sa.Column("start_date", sa.Date(), nullable=True))
        if not _column_exists(inspector, "employee_availability_requests", "end_date"):
            op.add_column("employee_availability_requests", sa.Column("end_date", sa.Date(), nullable=True))
        if not _column_exists(inspector, "employee_availability_requests", "note"):
            op.add_column("employee_availability_requests", sa.Column("note", sa.Text(), nullable=True))

    if not _table_exists(inspector, "audit_events"):
        op.create_table(
            "audit_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(length=120), nullable=False),
            sa.Column("entity_type", sa.String(length=120), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_audit_events_id"), "audit_events", ["id"], unique=False)
        op.create_index(op.f("ix_audit_events_organization_id"), "audit_events", ["organization_id"], unique=False)
        op.create_index(op.f("ix_audit_events_actor_user_id"), "audit_events", ["actor_user_id"], unique=False)
        op.create_index(op.f("ix_audit_events_action"), "audit_events", ["action"], unique=False)
        op.create_index(op.f("ix_audit_events_entity_id"), "audit_events", ["entity_id"], unique=False)
        op.create_index(op.f("ix_audit_events_created_at"), "audit_events", ["created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "audit_events"):
        op.drop_index(op.f("ix_audit_events_created_at"), table_name="audit_events")
        op.drop_index(op.f("ix_audit_events_entity_id"), table_name="audit_events")
        op.drop_index(op.f("ix_audit_events_action"), table_name="audit_events")
        op.drop_index(op.f("ix_audit_events_actor_user_id"), table_name="audit_events")
        op.drop_index(op.f("ix_audit_events_organization_id"), table_name="audit_events")
        op.drop_index(op.f("ix_audit_events_id"), table_name="audit_events")
        op.drop_table("audit_events")
