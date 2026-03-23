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


class ShiftCreate(BaseModel):
    organization_id: int
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
