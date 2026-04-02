from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import (
    AvailabilityStatus,
    CoverageDaypart,
    IntegrationProvider,
    IntegrationStatus,
    ShiftChangeStatus,
    ShiftChangeType,
    TimeOffStatus,
    UserRole,
)


class OrganizationCreate(BaseModel):
    name: str
    timezone: str = "America/Chicago"
    admin_name: str
    admin_email: EmailStr
    admin_password: str = Field(min_length=8, max_length=128)


class UserCreate(BaseModel):
    organization_id: int
    full_name: str
    email: Optional[EmailStr] = None
    role: UserRole
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    employee_number: Optional[str] = Field(default=None, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9-]+$")
    pin_code: Optional[str] = Field(default=None, min_length=4, max_length=12, pattern=r"^\d{4,12}$")
    job_title: Optional[str] = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    full_name: str
    email: Optional[str]
    role: UserRole
    is_active: bool
    employee_number: Optional[str] = None
    job_title: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: str
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    employee_number: Optional[str] = Field(default=None, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9-]+$")
    pin_code: Optional[str] = Field(default=None, min_length=4, max_length=12, pattern=r"^\d{4,12}$")
    job_title: Optional[str] = None
    is_active: bool = True


class EmployeeSelfProfileRead(BaseModel):
    employee_id: int
    full_name: str
    employee_number: Optional[str] = None
    job_title: Optional[str] = None
    preferred_weekly_hours: Optional[int] = None
    preferred_shift_notes: Optional[str] = None


class EmployeeSelfProfileUpdate(BaseModel):
    preferred_weekly_hours: Optional[int] = None
    preferred_shift_notes: Optional[str] = None


class ShiftCreate(BaseModel):
    organization_id: int
    employee_id: int
    shift_date: date
    start_at: datetime
    end_at: datetime
    location_name: Optional[str] = None
    role_label: Optional[str] = None


class ShiftUpdate(BaseModel):
    employee_id: int
    shift_date: date
    start_at: datetime
    end_at: datetime
    location_name: Optional[str] = None
    role_label: Optional[str] = None


class ShiftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    employee_id: int
    shift_date: date
    start_at: datetime
    end_at: datetime
    location_name: Optional[str]
    role_label: Optional[str]
    is_published: bool
    published_at: Optional[datetime]
    published_by_name: Optional[str]


class SchedulePublishRequest(BaseModel):
    week_start: date
    force_publish: bool = False


class SchedulePublishResponse(BaseModel):
    message: str
    week_start: date
    week_end: date
    published_shift_count: int


class SchedulePublicationRead(BaseModel):
    id: int
    organization_id: int
    week_start: date
    week_end: date
    action: str
    shift_count: int
    published_by_name: str
    comment: Optional[str] = None
    created_at: datetime
    acknowledged_count: int = 0


class ScheduleAcknowledgmentCreate(BaseModel):
    organization_id: int
    employee_id: int
    week_start: date


class ScheduleAcknowledgmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    employee_id: int
    week_start: date
    acknowledged_at: datetime


class SchedulePublicationCommentUpdate(BaseModel):
    comment: Optional[str] = None


class ScheduleRestoreResponse(BaseModel):
    message: str
    week_start: date
    week_end: date
    restored_shift_count: int


class AvailabilityRequestCreate(BaseModel):
    organization_id: int
    employee_id: int
    weekday: Optional[int] = Field(default=None, ge=0, le=6)
    start_time: str
    end_time: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    note: Optional[str] = None


class AvailabilityRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    employee_id: int
    weekday: Optional[int]
    start_time: str
    end_time: str
    start_date: Optional[date]
    end_date: Optional[date]
    note: Optional[str]
    status: AvailabilityStatus
    manager_response: Optional[str]
    created_at: datetime


class AvailabilityRequestUpdate(BaseModel):
    status: AvailabilityStatus
    manager_response: Optional[str] = None


class ShiftChangeRequestCreate(BaseModel):
    organization_id: int
    shift_id: int
    requester_employee_id: int
    request_type: ShiftChangeType
    note: str


class ShiftChangeRequestUpdate(BaseModel):
    status: ShiftChangeStatus
    manager_response: Optional[str] = None
    replacement_employee_id: Optional[int] = None


class ShiftChangeClaimCreate(BaseModel):
    employee_id: int


class ShiftChangeRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    shift_id: int
    requester_employee_id: int
    request_type: ShiftChangeType
    note: str
    status: ShiftChangeStatus
    manager_response: Optional[str]
    replacement_employee_id: Optional[int]
    created_at: datetime
    reviewed_at: Optional[datetime]
    shift_date: date
    shift_start_at: datetime
    shift_end_at: datetime
    requester_name: str
    replacement_employee_name: Optional[str] = None


class CoverageTargetCreate(BaseModel):
    organization_id: int
    weekday: int = Field(ge=0, le=6)
    daypart: CoverageDaypart
    role_label: Optional[str] = None
    required_headcount: int = Field(ge=1, le=100)


class CoverageTargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    weekday: int
    daypart: CoverageDaypart
    role_label: Optional[str]
    required_headcount: int
    created_at: datetime


class NoteCreate(BaseModel):
    organization_id: int
    employee_id: Optional[int] = None
    title: str
    body: str
    is_active: bool = True
    show_at_clock_in: bool = True


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    employee_id: Optional[int]
    title: str
    body: str
    is_active: bool
    show_at_clock_in: bool
    created_at: datetime


class NoteUpdate(BaseModel):
    employee_id: Optional[int] = None
    title: str
    body: str
    is_active: bool = True
    show_at_clock_in: bool = True


class ClockAction(BaseModel):
    organization_id: int
    employee_number: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9-]+$")
    pin_code: str = Field(min_length=4, max_length=12, pattern=r"^\d{4,12}$")
    source: str = Field(default="tablet", min_length=1, max_length=64)


class TimeEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    employee_id: int
    clock_in_at: datetime
    clock_out_at: Optional[datetime]
    clock_in_source: str
    clock_out_source: Optional[str]
    notes: Optional[str]
    approved: bool


class TimeEntryUpdate(BaseModel):
    approved: bool
    notes: Optional[str] = None
    clock_out_at: Optional[datetime] = None


class ReportRecipientCreate(BaseModel):
    organization_id: int
    email: EmailStr
    report_type: str = Field(min_length=1, max_length=120)


class ReportRecipientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    email: str
    report_type: str
    is_active: bool
    created_at: datetime


class IntegrationConnectionCreate(BaseModel):
    organization_id: int
    provider: IntegrationProvider
    status: IntegrationStatus = IntegrationStatus.PENDING
    settings: Optional[dict] = None


class IntegrationConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    provider: IntegrationProvider
    status: IntegrationStatus
    settings: Optional[dict]
    last_synced_at: Optional[datetime]


class QuickBooksConnectRequest(BaseModel):
    organization_id: int
    realm_id: Optional[str] = None
    company_name: Optional[str] = None


class QuickBooksAuthorizationRead(BaseModel):
    authorization_url: str
    state: str


class QuickBooksConfigStatus(BaseModel):
    configured: bool
    client_id_present: bool
    client_secret_present: bool
    redirect_uri: str
    environment: str
    scopes: list[str]


class QuickBooksExportRequest(BaseModel):
    start_date: date
    end_date: date


class QuickBooksActionResponse(BaseModel):
    message: str
    integration: IntegrationConnectionRead
    export_summary: Optional[dict] = None


class ClockResponse(BaseModel):
    status: str
    employee_name: str
    entry: TimeEntryRead
    schedule: list[ShiftRead]
    notes: list[NoteRead]


class ClockLookupResponse(BaseModel):
    employee_name: str
    employee_id: int
    schedule: list[ShiftRead]
    notes: list[NoteRead]


class LoginRequest(BaseModel):
    organization_id: int
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    message: str
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class DashboardSummary(BaseModel):
    organization_id: int
    active_employees: int
    currently_clocked_in: int
    report_recipients: int
    connected_integrations: int
    pending_notifications: int


class NotificationRead(BaseModel):
    key: str
    category: str
    title: str
    detail: str
    created_at: Optional[datetime] = None
    target_tab: Optional[str] = None
    target_id: Optional[int] = None


class SetupChecklistItem(BaseModel):
    key: str
    label: str
    complete: bool
    detail: str


class SetupOverview(BaseModel):
    organization_id: int
    organization_name: str
    timezone: str
    admin_count: int
    manager_count: int
    employee_count: int
    scheduled_shift_count: int
    note_count: int
    report_recipient_count: int
    time_entry_count: int
    quickbooks_configured: bool
    quickbooks_connected: bool
    checklist: list[SetupChecklistItem]


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    actor_user_id: Optional[int]
    action: str
    entity_type: str
    entity_id: Optional[int]
    detail: Optional[str]
    created_at: datetime


class TimeOffRequestCreate(BaseModel):
    organization_id: int
    employee_id: int
    start_date: date
    end_date: date
    reason: str


class TimeOffRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    employee_id: int
    start_date: date
    end_date: date
    reason: str
    status: TimeOffStatus
    manager_response: Optional[str]
    created_at: datetime


class TimeOffRequestUpdate(BaseModel):
    status: TimeOffStatus
    manager_response: Optional[str] = None
