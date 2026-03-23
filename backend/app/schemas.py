from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models import IntegrationProvider, IntegrationStatus, UserRole


class OrganizationCreate(BaseModel):
    name: str
    timezone: str = "America/Chicago"
    admin_name: str
    admin_email: EmailStr
    admin_password: str


class UserCreate(BaseModel):
    organization_id: int
    full_name: str
    email: Optional[EmailStr] = None
    role: UserRole
    password: Optional[str] = None
    employee_number: Optional[str] = None
    pin_code: Optional[str] = None
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
    password: Optional[str] = None
    employee_number: Optional[str] = None
    pin_code: Optional[str] = None
    job_title: Optional[str] = None
    is_active: bool = True


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
    employee_number: str
    pin_code: str
    source: str = "tablet"


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


class ReportRecipientCreate(BaseModel):
    organization_id: int
    email: EmailStr
    report_type: str


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
    password: str


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
