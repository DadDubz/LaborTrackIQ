from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import Base, engine, get_db
from app.models import (
    EmployeeProfile,
    IntegrationConnection,
    IntegrationProvider,
    IntegrationStatus,
    ManagerNote,
    Organization,
    ReportSubscription,
    ScheduleShift,
    TimeEntry,
    User,
    UserRole,
)
from app.schemas import (
    ClockAction,
    ClockLookupResponse,
    ClockResponse,
    DashboardSummary,
    IntegrationConnectionCreate,
    IntegrationConnectionRead,
    LoginRequest,
    LoginResponse,
    NoteCreate,
    NoteRead,
    NoteUpdate,
    OrganizationCreate,
    QuickBooksActionResponse,
    QuickBooksConnectRequest,
    QuickBooksExportRequest,
    ReportRecipientCreate,
    ShiftCreate,
    ShiftRead,
    ShiftUpdate,
    TimeEntryRead,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.security import create_access_token, decode_access_token, hash_password, verify_password


Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    payload = decode_access_token(authorization.split(" ", 1)[1])
    user = db.get(User, payload["user_id"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not available.")
    return user


def require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {UserRole.ADMIN, UserRole.MANAGER}:
        raise HTTPException(status_code=403, detail="Admin or manager access required.")
    return current_user


def validate_organization_access(organization_id: int, current_user: User) -> None:
    if current_user.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="Cross-organization access is not allowed.")


def find_employee_by_clock_credentials(
    organization_id: int, employee_number: str, pin_code: str, db: Session
) -> User:
    profile = db.scalar(
        select(EmployeeProfile)
        .join(User)
        .where(
            and_(
                User.organization_id == organization_id,
                User.is_active.is_(True),
                EmployeeProfile.employee_number == employee_number,
                EmployeeProfile.pin_code == pin_code,
            )
        )
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Employee credentials not found.")

    employee = db.get(User, profile.user_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")
    return employee


def load_employee_clock_context(employee_id: int, organization_id: int, db: Session):
    shifts = db.scalars(
        select(ScheduleShift)
        .where(and_(ScheduleShift.employee_id == employee_id, ScheduleShift.shift_date >= date.today()))
        .order_by(ScheduleShift.start_at.asc())
    ).all()
    notes = db.scalars(
        select(ManagerNote)
        .where(
            and_(
                ManagerNote.organization_id == organization_id,
                ManagerNote.is_active.is_(True),
                ManagerNote.show_at_clock_in.is_(True),
                or_(ManagerNote.employee_id == employee_id, ManagerNote.employee_id.is_(None)),
            )
        )
        .order_by(ManagerNote.created_at.desc())
    ).all()
    return shifts, notes


def serialize_user(user: User) -> UserRead:
    profile = user.employee_profile
    return UserRead(
        id=user.id,
        organization_id=user.organization_id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        employee_number=profile.employee_number if profile else None,
        job_title=profile.job_title if profile else None,
    )


def get_employee_profile_or_404(user_id: int, db: Session) -> EmployeeProfile:
    profile = db.scalar(select(EmployeeProfile).where(EmployeeProfile.user_id == user_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Employee profile not found.")
    return profile


def get_user_for_admin(user_id: int, current_user: User, db: Session) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    validate_organization_access(user.organization_id, current_user)
    return user


def get_shift_for_admin(shift_id: int, current_user: User, db: Session) -> ScheduleShift:
    shift = db.get(ScheduleShift, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found.")
    validate_organization_access(shift.organization_id, current_user)
    return shift


def get_note_for_admin(note_id: int, current_user: User, db: Session) -> ManagerNote:
    note = db.get(ManagerNote, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    validate_organization_access(note.organization_id, current_user)
    return note


def get_integration_for_admin(integration_id: int, current_user: User, db: Session) -> IntegrationConnection:
    integration = db.get(IntegrationConnection, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found.")
    validate_organization_access(integration.organization_id, current_user)
    return integration


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.app_name}


@app.post(f"{settings.api_prefix}/organizations", response_model=dict)
def create_organization(payload: OrganizationCreate, db: Session = Depends(get_db)):
    organization = Organization(name=payload.name, timezone=payload.timezone)
    db.add(organization)
    db.flush()

    admin = User(
        organization_id=organization.id,
        full_name=payload.admin_name,
        email=payload.admin_email,
        role=UserRole.ADMIN,
        password_hash=hash_password(payload.admin_password),
    )
    db.add(admin)
    db.commit()

    return {
        "organization_id": organization.id,
        "admin_user_id": admin.id,
        "message": "Organization and admin account created.",
    }


@app.post(f"{settings.api_prefix}/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(
        select(User).where(
            and_(
                User.organization_id == payload.organization_id,
                User.email == payload.email,
                User.is_active.is_(True),
            )
        )
    )
    if not user or user.role not in {UserRole.ADMIN, UserRole.MANAGER, UserRole.REPORT_VIEWER}:
        raise HTTPException(status_code=401, detail="Invalid login credentials.")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid login credentials.")

    return LoginResponse(
        message="Login successful.",
        access_token=create_access_token(user.id, user.organization_id, user.role.value),
        user=serialize_user(user),
    )


@app.post(f"{settings.api_prefix}/users", response_model=UserRead)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(payload.organization_id, current_user)
    if payload.role != UserRole.EMPLOYEE and not payload.password:
        raise HTTPException(status_code=400, detail="Non-employee users require a password.")

    user = User(
        organization_id=payload.organization_id,
        full_name=payload.full_name,
        email=payload.email,
        role=payload.role,
        password_hash=hash_password(payload.password) if payload.password else None,
    )
    db.add(user)
    db.flush()

    if payload.role == UserRole.EMPLOYEE:
        if not payload.employee_number or not payload.pin_code:
            raise HTTPException(status_code=400, detail="Employees require employee_number and pin_code.")
        db.add(
            EmployeeProfile(
                user_id=user.id,
                employee_number=payload.employee_number,
                pin_code=payload.pin_code,
                job_title=payload.job_title,
            )
        )

    db.commit()
    db.refresh(user)
    return serialize_user(user)


@app.get(f"{settings.api_prefix}/organizations/{{organization_id}}/users", response_model=list[UserRead])
def list_users(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    users = db.scalars(select(User).where(User.organization_id == organization_id).order_by(User.full_name.asc())).all()
    return [serialize_user(user) for user in users]


@app.put(f"{settings.api_prefix}/users/{{user_id}}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    user = get_user_for_admin(user_id, current_user, db)
    user.full_name = payload.full_name
    user.email = payload.email
    user.is_active = payload.is_active

    if payload.password:
        user.password_hash = hash_password(payload.password)

    if user.role == UserRole.EMPLOYEE:
        profile = get_employee_profile_or_404(user.id, db)
        if not payload.employee_number or not payload.pin_code:
            raise HTTPException(status_code=400, detail="Employees require employee_number and pin_code.")
        profile.employee_number = payload.employee_number
        profile.pin_code = payload.pin_code
        profile.job_title = payload.job_title

    db.commit()
    db.refresh(user)
    return serialize_user(user)


@app.delete(f"{settings.api_prefix}/users/{{user_id}}", response_model=dict)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    user = get_user_for_admin(user_id, current_user, db)
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")

    user.is_active = False
    db.commit()
    return {"message": f"{user.full_name} archived successfully."}


@app.post(f"{settings.api_prefix}/shifts", response_model=ShiftRead)
def create_shift(
    payload: ShiftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(payload.organization_id, current_user)
    shift = ScheduleShift(**payload.model_dump())
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


@app.get(f"{settings.api_prefix}/organizations/{{organization_id}}/shifts", response_model=list[ShiftRead])
def list_shifts(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    shifts = db.scalars(
        select(ScheduleShift).where(ScheduleShift.organization_id == organization_id).order_by(ScheduleShift.start_at.asc())
    ).all()
    return list(shifts)


@app.put(f"{settings.api_prefix}/shifts/{{shift_id}}", response_model=ShiftRead)
def update_shift(
    shift_id: int,
    payload: ShiftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    shift = get_shift_for_admin(shift_id, current_user, db)
    shift.employee_id = payload.employee_id
    shift.shift_date = payload.shift_date
    shift.start_at = payload.start_at
    shift.end_at = payload.end_at
    shift.location_name = payload.location_name
    shift.role_label = payload.role_label
    db.commit()
    db.refresh(shift)
    return shift


@app.delete(f"{settings.api_prefix}/shifts/{{shift_id}}", response_model=dict)
def delete_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    shift = get_shift_for_admin(shift_id, current_user, db)
    db.delete(shift)
    db.commit()
    return {"message": "Shift deleted successfully."}


@app.get(f"{settings.api_prefix}/employees/{{employee_id}}/schedule", response_model=list[ShiftRead])
def get_employee_schedule(employee_id: int, db: Session = Depends(get_db)):
    shifts = db.scalars(
        select(ScheduleShift)
        .where(and_(ScheduleShift.employee_id == employee_id, ScheduleShift.shift_date >= date.today()))
        .order_by(ScheduleShift.start_at.asc())
    ).all()
    return list(shifts)


@app.post(f"{settings.api_prefix}/notes", response_model=NoteRead)
def create_note(
    payload: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(payload.organization_id, current_user)
    note = ManagerNote(**payload.model_dump())
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@app.get(f"{settings.api_prefix}/organizations/{{organization_id}}/notes", response_model=list[NoteRead])
def list_notes(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    notes = db.scalars(
        select(ManagerNote).where(ManagerNote.organization_id == organization_id).order_by(ManagerNote.created_at.desc())
    ).all()
    return list(notes)


@app.put(f"{settings.api_prefix}/notes/{{note_id}}", response_model=NoteRead)
def update_note(
    note_id: int,
    payload: NoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    note = get_note_for_admin(note_id, current_user, db)
    note.employee_id = payload.employee_id
    note.title = payload.title
    note.body = payload.body
    note.is_active = payload.is_active
    note.show_at_clock_in = payload.show_at_clock_in
    db.commit()
    db.refresh(note)
    return note


@app.delete(f"{settings.api_prefix}/notes/{{note_id}}", response_model=dict)
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    note = get_note_for_admin(note_id, current_user, db)
    db.delete(note)
    db.commit()
    return {"message": "Note deleted successfully."}


@app.post(f"{settings.api_prefix}/clock/lookup", response_model=ClockLookupResponse)
def lookup_clock_context(payload: ClockAction, db: Session = Depends(get_db)):
    employee = find_employee_by_clock_credentials(payload.organization_id, payload.employee_number, payload.pin_code, db)
    shifts, notes = load_employee_clock_context(employee.id, payload.organization_id, db)
    return ClockLookupResponse(
        employee_name=employee.full_name,
        employee_id=employee.id,
        schedule=[ShiftRead.model_validate(shift) for shift in shifts],
        notes=[NoteRead.model_validate(note) for note in notes],
    )


@app.post(f"{settings.api_prefix}/clock/in-out", response_model=ClockResponse)
def clock_in_out(payload: ClockAction, db: Session = Depends(get_db)):
    employee = find_employee_by_clock_credentials(payload.organization_id, payload.employee_number, payload.pin_code, db)
    active_entry = db.scalar(
        select(TimeEntry)
        .where(and_(TimeEntry.employee_id == employee.id, TimeEntry.clock_out_at.is_(None)))
        .order_by(TimeEntry.clock_in_at.desc())
    )

    status = "clocked_in"
    if active_entry:
        active_entry.clock_out_at = datetime.utcnow()
        active_entry.clock_out_source = payload.source
        entry = active_entry
        status = "clocked_out"
    else:
        entry = TimeEntry(
            organization_id=payload.organization_id,
            employee_id=employee.id,
            clock_in_at=datetime.utcnow(),
            clock_in_source=payload.source,
        )
        db.add(entry)

    db.commit()
    db.refresh(entry)

    shifts, notes = load_employee_clock_context(employee.id, payload.organization_id, db)
    return ClockResponse(
        status=status,
        employee_name=employee.full_name,
        entry=TimeEntryRead.model_validate(entry),
        schedule=[ShiftRead.model_validate(shift) for shift in shifts],
        notes=[NoteRead.model_validate(note) for note in notes],
    )


@app.post(f"{settings.api_prefix}/report-recipients", response_model=dict)
def create_report_recipient(
    payload: ReportRecipientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(payload.organization_id, current_user)
    recipient = ReportSubscription(**payload.model_dump())
    db.add(recipient)
    db.commit()
    db.refresh(recipient)
    return {"id": recipient.id, "message": "Report recipient added."}


@app.post(f"{settings.api_prefix}/integrations", response_model=IntegrationConnectionRead)
def create_integration(
    payload: IntegrationConnectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(payload.organization_id, current_user)
    integration = IntegrationConnection(**payload.model_dump())
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return integration


@app.post(
    f"{settings.api_prefix}/organizations/{{organization_id}}/integrations/quickbooks/connect",
    response_model=QuickBooksActionResponse,
)
def connect_quickbooks(
    organization_id: int,
    payload: QuickBooksConnectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    if payload.organization_id != organization_id:
        raise HTTPException(status_code=400, detail="Organization mismatch.")

    integration = db.scalar(
        select(IntegrationConnection).where(
            and_(
                IntegrationConnection.organization_id == organization_id,
                IntegrationConnection.provider == IntegrationProvider.QUICKBOOKS,
            )
        )
    )
    settings_payload = {
        "realm_id": payload.realm_id or f"realm-{organization_id}",
        "company_name": payload.company_name or "Demo Diner Books",
        "oauth_state": "simulated-authorized",
        "last_export_status": "ready",
    }

    if integration:
        integration.status = IntegrationStatus.CONNECTED
        integration.settings = settings_payload
        integration.credentials_ref = "quickbooks-demo-token"
        integration.last_synced_at = datetime.utcnow()
    else:
        integration = IntegrationConnection(
            organization_id=organization_id,
            provider=IntegrationProvider.QUICKBOOKS,
            status=IntegrationStatus.CONNECTED,
            credentials_ref="quickbooks-demo-token",
            settings=settings_payload,
            last_synced_at=datetime.utcnow(),
        )
        db.add(integration)

    db.commit()
    db.refresh(integration)
    return QuickBooksActionResponse(
        message="QuickBooks connected successfully.",
        integration=IntegrationConnectionRead.model_validate(integration),
    )


@app.post(f"{settings.api_prefix}/integrations/{{integration_id}}/disconnect", response_model=QuickBooksActionResponse)
def disconnect_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    integration = get_integration_for_admin(integration_id, current_user, db)
    integration.status = IntegrationStatus.DISCONNECTED
    integration.credentials_ref = None
    integration.settings = {
        **(integration.settings or {}),
        "last_export_status": "disconnected",
    }
    db.commit()
    db.refresh(integration)
    return QuickBooksActionResponse(
        message=f"{integration.provider.value.title()} disconnected.",
        integration=IntegrationConnectionRead.model_validate(integration),
    )


@app.post(f"{settings.api_prefix}/integrations/{{integration_id}}/export-labor", response_model=QuickBooksActionResponse)
def export_integration_labor(
    integration_id: int,
    payload: QuickBooksExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    integration = get_integration_for_admin(integration_id, current_user, db)
    if integration.provider != IntegrationProvider.QUICKBOOKS:
        raise HTTPException(status_code=400, detail="This export is only implemented for QuickBooks.")
    if integration.status != IntegrationStatus.CONNECTED:
        raise HTTPException(status_code=400, detail="Connect QuickBooks before exporting labor.")
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date.")

    start_dt = datetime.combine(payload.start_date, datetime.min.time())
    end_dt = datetime.combine(payload.end_date, datetime.max.time())
    entries = db.scalars(
        select(TimeEntry).where(
            and_(
                TimeEntry.organization_id == integration.organization_id,
                TimeEntry.clock_in_at >= start_dt,
                TimeEntry.clock_in_at <= end_dt,
            )
        )
    ).all()

    exported_entries = 0
    exported_hours = 0.0
    for entry in entries:
        if entry.clock_out_at:
            exported_entries += 1
            exported_hours += (entry.clock_out_at - entry.clock_in_at).total_seconds() / 3600

    integration.last_synced_at = datetime.utcnow()
    integration.settings = {
        **(integration.settings or {}),
        "last_export_status": "completed",
        "last_export_range": {
            "start_date": payload.start_date.isoformat(),
            "end_date": payload.end_date.isoformat(),
        },
        "last_export_totals": {
            "entries": exported_entries,
            "hours": round(exported_hours, 2),
        },
    }
    db.commit()
    db.refresh(integration)

    return QuickBooksActionResponse(
        message="QuickBooks labor export simulated successfully.",
        integration=IntegrationConnectionRead.model_validate(integration),
        export_summary={
            "entries": exported_entries,
            "hours": round(exported_hours, 2),
            "start_date": payload.start_date.isoformat(),
            "end_date": payload.end_date.isoformat(),
        },
    )


@app.get(f"{settings.api_prefix}/organizations/{{organization_id}}/integrations", response_model=list[IntegrationConnectionRead])
def list_integrations(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    integrations = db.scalars(select(IntegrationConnection).where(IntegrationConnection.organization_id == organization_id)).all()
    return list(integrations)


@app.get(f"{settings.api_prefix}/organizations/{{organization_id}}/dashboard-summary", response_model=DashboardSummary)
def get_dashboard_summary(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    active_employees = db.scalar(
        select(func.count(User.id)).where(
            and_(User.organization_id == organization_id, User.role == UserRole.EMPLOYEE, User.is_active.is_(True))
        )
    ) or 0
    currently_clocked_in = db.scalar(
        select(func.count(TimeEntry.id)).where(
            and_(TimeEntry.organization_id == organization_id, TimeEntry.clock_out_at.is_(None))
        )
    ) or 0
    report_recipients = db.scalar(
        select(func.count(ReportSubscription.id)).where(
            and_(ReportSubscription.organization_id == organization_id, ReportSubscription.is_active.is_(True))
        )
    ) or 0
    connected_integrations = db.scalar(
        select(func.count(IntegrationConnection.id)).where(
            and_(
                IntegrationConnection.organization_id == organization_id,
                IntegrationConnection.status == IntegrationStatus.CONNECTED,
            )
        )
    ) or 0

    return DashboardSummary(
        organization_id=organization_id,
        active_employees=active_employees,
        currently_clocked_in=currently_clocked_in,
        report_recipients=report_recipients,
        connected_integrations=connected_integrations,
    )


@app.post(f"{settings.api_prefix}/bootstrap/demo", response_model=dict)
def bootstrap_demo(db: Session = Depends(get_db)):
    existing_org = db.scalar(select(Organization).where(Organization.name == "Demo Diner"))
    if existing_org:
        demo_admin = db.scalar(
            select(User).where(
                and_(User.organization_id == existing_org.id, User.full_name == "Alex Owner", User.role == UserRole.ADMIN)
            )
        )
        demo_manager = db.scalar(
            select(User).where(
                and_(User.organization_id == existing_org.id, User.full_name == "Jordan Manager", User.role == UserRole.MANAGER)
            )
        )
        demo_employee = db.scalar(
            select(User).where(
                and_(
                    User.organization_id == existing_org.id,
                    User.full_name == "Taylor Employee",
                    User.role == UserRole.EMPLOYEE,
                )
            )
        )
        if demo_admin:
            demo_admin.email = "admin@demodiner.com"
            demo_admin.password_hash = hash_password("admin1234")
        if demo_manager:
            demo_manager.email = "manager@demodiner.com"
            demo_manager.password_hash = hash_password("manager1234")
        if demo_employee:
            demo_employee.email = "taylor@demodiner.com"
            profile = db.scalar(select(EmployeeProfile).where(EmployeeProfile.user_id == demo_employee.id))
            if profile:
                profile.employee_number = "1001"
                profile.pin_code = "1234"
        db.commit()
        return {
            "organization_id": existing_org.id,
            "admin_email": "admin@demodiner.com",
            "admin_password": "admin1234",
            "employee_number": "1001",
            "employee_pin": "1234",
            "message": "Demo data already exists.",
        }

    organization = Organization(name="Demo Diner", timezone="America/Chicago")
    db.add(organization)
    db.flush()

    admin = User(
        organization_id=organization.id,
        full_name="Alex Owner",
        email="admin@demodiner.com",
        role=UserRole.ADMIN,
        password_hash=hash_password("admin1234"),
    )
    manager = User(
        organization_id=organization.id,
        full_name="Jordan Manager",
        email="manager@demodiner.com",
        role=UserRole.MANAGER,
        password_hash=hash_password("manager1234"),
    )
    employee = User(
        organization_id=organization.id,
        full_name="Taylor Employee",
        email="taylor@demodiner.com",
        role=UserRole.EMPLOYEE,
    )
    db.add_all([admin, manager, employee])
    db.flush()

    db.add(
        EmployeeProfile(
            user_id=employee.id,
            employee_number="1001",
            pin_code="1234",
            job_title="Front Counter",
        )
    )
    db.add_all(
        [
            ScheduleShift(
                organization_id=organization.id,
                employee_id=employee.id,
                shift_date=date.today(),
                start_at=datetime.utcnow().replace(hour=14, minute=0, second=0, microsecond=0),
                end_at=datetime.utcnow().replace(hour=22, minute=0, second=0, microsecond=0),
                location_name="Main Store",
                role_label="Front Counter",
            ),
            ManagerNote(
                organization_id=organization.id,
                employee_id=None,
                title="Opening Priorities",
                body="Check drawer balances, refill ice, and confirm the lunch prep list is complete.",
            ),
            ReportSubscription(
                organization_id=organization.id,
                email="owner@demodiner.com",
                report_type="daily_labor_summary",
            ),
            IntegrationConnection(
                organization_id=organization.id,
                provider=IntegrationProvider.QUICKBOOKS,
                status=IntegrationStatus.CONNECTED,
                settings={"export_mode": "labor_summary"},
            ),
        ]
    )
    db.commit()

    return {
        "organization_id": organization.id,
        "admin_email": "admin@demodiner.com",
        "admin_password": "admin1234",
        "employee_number": "1001",
        "employee_pin": "1234",
        "message": "Demo organization created.",
    }
