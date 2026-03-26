from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum as SqlEnum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"
    REPORT_VIEWER = "report_viewer"


class IntegrationProvider(str, Enum):
    QUICKBOOKS = "quickbooks"
    XERO = "xero"
    GUSTO = "gusto"
    ADP = "adp"
    RESTAURANT365 = "restaurant365"


class IntegrationStatus(str, Enum):
    DISCONNECTED = "disconnected"
    PENDING = "pending"
    CONNECTED = "connected"
    ERROR = "error"


class TimeOffStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class AvailabilityStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class ShiftChangeType(str, Enum):
    PICKUP = "pickup"
    SWAP = "swap"


class ShiftChangeStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class CoverageDaypart(str, Enum):
    MORNING = "morning"
    LUNCH = "lunch"
    CLOSE = "close"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Chicago")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="organization")
    notes: Mapped[list["ManagerNote"]] = relationship(back_populates="organization")
    shifts: Mapped[list["ScheduleShift"]] = relationship(back_populates="organization")
    time_entries: Mapped[list["TimeEntry"]] = relationship(back_populates="organization")
    time_off_requests: Mapped[list["TimeOffRequest"]] = relationship(back_populates="organization")
    availability_requests: Mapped[list["EmployeeAvailabilityRequest"]] = relationship(back_populates="organization")
    coverage_targets: Mapped[list["ScheduleCoverageTarget"]] = relationship(back_populates="organization")
    shift_change_requests: Mapped[list["ShiftChangeRequest"]] = relationship(back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(SqlEnum(UserRole), nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="users")
    employee_profile: Mapped["EmployeeProfile"] = relationship(back_populates="user", uselist=False)
    scheduled_shifts: Mapped[list["ScheduleShift"]] = relationship(back_populates="employee")
    time_entries: Mapped[list["TimeEntry"]] = relationship(back_populates="employee")
    assigned_notes: Mapped[list["ManagerNote"]] = relationship(back_populates="employee")
    time_off_requests: Mapped[list["TimeOffRequest"]] = relationship(back_populates="employee")
    availability_requests: Mapped[list["EmployeeAvailabilityRequest"]] = relationship(back_populates="employee")
    submitted_shift_change_requests: Mapped[list["ShiftChangeRequest"]] = relationship(
        back_populates="requester",
        foreign_keys="ShiftChangeRequest.requester_employee_id",
    )


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    employee_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    pin_code: Mapped[str] = mapped_column(String(12), nullable=False)
    job_title: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    quickbooks_employee_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    user: Mapped["User"] = relationship(back_populates="employee_profile")


class ScheduleShift(Base):
    __tablename__ = "schedule_shifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    shift_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    location_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    role_label: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    published_by_name: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="shifts")
    employee: Mapped["User"] = relationship(back_populates="scheduled_shifts")


class ScheduleCoverageTarget(Base):
    __tablename__ = "schedule_coverage_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    daypart: Mapped[CoverageDaypart] = mapped_column(SqlEnum(CoverageDaypart), nullable=False)
    role_label: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    required_headcount: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="coverage_targets")


class TimeEntry(Base):
    __tablename__ = "time_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    clock_in_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    clock_out_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    clock_in_source: Mapped[str] = mapped_column(String(64), default="tablet")
    clock_out_source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)

    organization: Mapped["Organization"] = relationship(back_populates="time_entries")
    employee: Mapped["User"] = relationship(back_populates="time_entries")


class EmployeeAvailabilityRequest(Base):
    __tablename__ = "employee_availability_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    status: Mapped[AvailabilityStatus] = mapped_column(SqlEnum(AvailabilityStatus), default=AvailabilityStatus.PENDING)
    manager_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="availability_requests")
    employee: Mapped["User"] = relationship(back_populates="availability_requests")


class ManagerNote(Base):
    __tablename__ = "manager_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    show_at_clock_in: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="notes")
    employee: Mapped["User"] = relationship(back_populates="assigned_notes")


class ReportSubscription(Base):
    __tablename__ = "report_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    report_type: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    provider: Mapped[IntegrationProvider] = mapped_column(SqlEnum(IntegrationProvider), nullable=False)
    status: Mapped[IntegrationStatus] = mapped_column(SqlEnum(IntegrationStatus), default=IntegrationStatus.DISCONNECTED)
    credentials_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class TimeOffRequest(Base):
    __tablename__ = "time_off_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TimeOffStatus] = mapped_column(SqlEnum(TimeOffStatus), default=TimeOffStatus.PENDING)
    manager_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="time_off_requests")
    employee: Mapped["User"] = relationship(back_populates="time_off_requests")


class ShiftChangeRequest(Base):
    __tablename__ = "shift_change_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey("schedule_shifts.id"), nullable=False, index=True)
    requester_employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    request_type: Mapped[ShiftChangeType] = mapped_column(SqlEnum(ShiftChangeType), default=ShiftChangeType.PICKUP)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ShiftChangeStatus] = mapped_column(SqlEnum(ShiftChangeStatus), default=ShiftChangeStatus.PENDING)
    manager_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    replacement_employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="shift_change_requests")
    requester: Mapped["User"] = relationship(
        back_populates="submitted_shift_change_requests",
        foreign_keys=[requester_employee_id],
    )
    shift: Mapped["ScheduleShift"] = relationship(foreign_keys=[shift_id])


class SchedulePublicationEvent(Base):
    __tablename__ = "schedule_publication_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    shift_count: Mapped[int] = mapped_column(Integer, default=0)
    published_by_name: Mapped[str] = mapped_column(String(180), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    snapshot_data: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ScheduleAcknowledgment(Base):
    __tablename__ = "schedule_acknowledgments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
