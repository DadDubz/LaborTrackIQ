from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import Base, engine, get_db
from app.models import (
    EmployeeAvailabilityRequest,
    EmployeeProfile,
    IntegrationConnection,
    IntegrationProvider,
    IntegrationStatus,
    ManagerNote,
    Organization,
    ReportSubscription,
    ScheduleAcknowledgment,
    ScheduleCoverageTarget,
    SchedulePublicationEvent,
    ScheduleShift,
    ShiftChangeRequest,
    ShiftChangeStatus,
    ShiftChangeType,
    TimeEntry,
    TimeOffStatus,
    AvailabilityStatus,
    TimeOffRequest,
    User,
    UserRole,
)
from app.schemas import (
    AvailabilityRequestCreate,
    AvailabilityRequestRead,
    AvailabilityRequestUpdate,
    ClockAction,
    CoverageTargetCreate,
    CoverageTargetRead,
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
    QuickBooksAuthorizationRead,
    QuickBooksConfigStatus,
    QuickBooksConnectRequest,
    QuickBooksExportRequest,
    ReportRecipientCreate,
    ScheduleAcknowledgmentCreate,
    ScheduleAcknowledgmentRead,
    SchedulePublicationCommentUpdate,
    SchedulePublicationRead,
    SchedulePublishRequest,
    SchedulePublishResponse,
    ScheduleRestoreResponse,
    ShiftChangeClaimCreate,
    ShiftChangeRequestCreate,
    ShiftChangeRequestRead,
    ShiftChangeRequestUpdate,
    ShiftCreate,
    ShiftRead,
    ShiftUpdate,
    NotificationRead,
    SetupChecklistItem,
    SetupOverview,
    TimeEntryRead,
    TimeOffRequestCreate,
    TimeOffRequestRead,
    TimeOffRequestUpdate,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.security import create_access_token, decode_access_token, hash_password, seal_secret, unseal_secret, verify_password
from app.services.quickbooks import (
    build_authorization_url,
    exchange_code_for_tokens,
    generate_state_token,
    refresh_tokens,
    token_expiry,
)


Base.metadata.create_all(bind=engine)


def ensure_schedule_shift_publish_columns() -> None:
    with engine.begin() as connection:
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(schedule_shifts)"))}
        if "is_published" not in columns:
            connection.execute(text("ALTER TABLE schedule_shifts ADD COLUMN is_published BOOLEAN DEFAULT 0"))
        if "published_at" not in columns:
            connection.execute(text("ALTER TABLE schedule_shifts ADD COLUMN published_at DATETIME"))
        if "published_by_name" not in columns:
            connection.execute(text("ALTER TABLE schedule_shifts ADD COLUMN published_by_name VARCHAR(180)"))
        publication_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(schedule_publication_events)"))}
        if publication_columns and "comment" not in publication_columns:
            connection.execute(text("ALTER TABLE schedule_publication_events ADD COLUMN comment TEXT"))
        coverage_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(schedule_coverage_targets)"))}
        if coverage_columns and "role_label" not in coverage_columns:
            connection.execute(text("ALTER TABLE schedule_coverage_targets ADD COLUMN role_label VARCHAR(120)"))


ensure_schedule_shift_publish_columns()

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
        .where(
            and_(
                ScheduleShift.employee_id == employee_id,
                ScheduleShift.shift_date >= date.today(),
                ScheduleShift.is_published.is_(True),
            )
        )
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


def week_end_from_start(week_start: date) -> date:
    return date.fromordinal(week_start.toordinal() + 6)


def resolve_daypart_for_time(value: datetime) -> str:
    hour = value.hour
    if hour < 11:
        return "morning"
    if hour < 16:
        return "lunch"
    return "close"


def weekday_for_schedule(value: date) -> int:
    return (value.weekday() + 1) % 7


def weekday_label(value: int) -> str:
    return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][value] if 0 <= value <= 6 else "Day"


def build_coverage_shortages(
    shifts: list[ScheduleShift],
    coverage_targets: list[ScheduleCoverageTarget],
) -> list[str]:
    shortages: list[str] = []
    for target in coverage_targets:
        scheduled_count = sum(
            1
            for shift in shifts
            if weekday_for_schedule(shift.shift_date) == target.weekday
            and resolve_daypart_for_time(shift.start_at) == target.daypart.value
            and (not target.role_label or (shift.role_label or "").strip().lower() == target.role_label.strip().lower())
        )
        if scheduled_count >= target.required_headcount:
            continue
        role_suffix = f" for {target.role_label}" if target.role_label else ""
        shortages.append(
            f"{target.daypart.value.title()} on weekday {target.weekday} is short by {target.required_headcount - scheduled_count}{role_suffix}."
        )
    return shortages


def build_shift_snapshot(shift: ScheduleShift) -> dict:
    return {
        "shift_id": shift.id,
        "employee_id": shift.employee_id,
        "shift_date": shift.shift_date.isoformat(),
        "start_at": shift.start_at.isoformat(),
        "end_at": shift.end_at.isoformat(),
        "location_name": shift.location_name,
        "role_label": shift.role_label,
        "is_published": shift.is_published,
        "published_at": shift.published_at.isoformat() if shift.published_at else None,
        "published_by_name": shift.published_by_name,
    }


def get_publication_event_for_admin(publication_id: int, current_user: User, db: Session) -> SchedulePublicationEvent:
    publication = db.get(SchedulePublicationEvent, publication_id)
    if not publication:
        raise HTTPException(status_code=404, detail="Schedule publication event not found.")
    validate_organization_access(publication.organization_id, current_user)
    return publication


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


def get_employee_or_404(employee_id: int, organization_id: int, db: Session) -> User:
    employee = db.get(User, employee_id)
    if not employee or employee.organization_id != organization_id or employee.role != UserRole.EMPLOYEE:
        raise HTTPException(status_code=404, detail="Employee not found.")
    return employee


def get_time_off_request_for_admin(request_id: int, current_user: User, db: Session) -> TimeOffRequest:
    request = db.get(TimeOffRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Time-off request not found.")
    validate_organization_access(request.organization_id, current_user)
    return request


def serialize_shift_change_request(request: ShiftChangeRequest, db: Session) -> ShiftChangeRequestRead:
    shift = db.get(ScheduleShift, request.shift_id)
    requester = db.get(User, request.requester_employee_id)
    replacement = db.get(User, request.replacement_employee_id) if request.replacement_employee_id else None
    if not shift or not requester:
        raise HTTPException(status_code=404, detail="Shift change request context is incomplete.")
    return ShiftChangeRequestRead(
        id=request.id,
        organization_id=request.organization_id,
        shift_id=request.shift_id,
        requester_employee_id=request.requester_employee_id,
        request_type=request.request_type,
        note=request.note,
        status=request.status,
        manager_response=request.manager_response,
        replacement_employee_id=request.replacement_employee_id,
        created_at=request.created_at,
        reviewed_at=request.reviewed_at,
        shift_date=shift.shift_date,
        shift_start_at=shift.start_at,
        shift_end_at=shift.end_at,
        requester_name=requester.full_name,
        replacement_employee_name=replacement.full_name if replacement else None,
    )


def build_admin_notifications(organization_id: int, db: Session) -> list[NotificationRead]:
    notifications: list[NotificationRead] = []

    pending_time_off = db.scalars(
        select(TimeOffRequest)
        .where(and_(TimeOffRequest.organization_id == organization_id, TimeOffRequest.status == TimeOffStatus.PENDING))
        .order_by(TimeOffRequest.created_at.desc())
        .limit(5)
    ).all()
    for request in pending_time_off:
        employee = db.get(User, request.employee_id)
        notifications.append(
            NotificationRead(
                key=f"time-off-{request.id}",
                category="time_off",
                title=f"Time-off request from {employee.full_name if employee else f'Employee {request.employee_id}'}",
                detail=f"{request.start_date.isoformat()} to {request.end_date.isoformat()}",
                created_at=request.created_at,
            )
        )

    pending_availability = db.scalars(
        select(EmployeeAvailabilityRequest)
        .where(
            and_(
                EmployeeAvailabilityRequest.organization_id == organization_id,
                EmployeeAvailabilityRequest.status == AvailabilityStatus.PENDING,
            )
        )
        .order_by(EmployeeAvailabilityRequest.created_at.desc())
        .limit(5)
    ).all()
    for request in pending_availability:
        employee = db.get(User, request.employee_id)
        notifications.append(
            NotificationRead(
                key=f"availability-{request.id}",
                category="availability",
                title=f"Availability request from {employee.full_name if employee else f'Employee {request.employee_id}'}",
                detail=f"{weekday_label(request.weekday)} {request.start_time}-{request.end_time}",
                created_at=request.created_at,
            )
        )

    pending_shift_changes = db.scalars(
        select(ShiftChangeRequest)
        .where(and_(ShiftChangeRequest.organization_id == organization_id, ShiftChangeRequest.status == ShiftChangeStatus.PENDING))
        .order_by(ShiftChangeRequest.created_at.desc())
        .limit(5)
    ).all()
    for request in pending_shift_changes:
        notifications.append(
            NotificationRead(
                key=f"shift-change-{request.id}",
                category="shift_change",
                title=f"{request.request_type.value.title()} request from {serialize_shift_change_request(request, db).requester_name}",
                detail=request.note,
                created_at=request.created_at,
            )
        )

    return sorted(notifications, key=lambda item: item.created_at or datetime.min, reverse=True)[:8]


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
    shift = ScheduleShift(**payload.model_dump(), is_published=False, published_at=None, published_by_name=None)
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
    shift.is_published = False
    db.commit()
    db.refresh(shift)
    return shift


@app.post(
    f"{settings.api_prefix}/organizations/{{organization_id}}/schedule/publish",
    response_model=SchedulePublishResponse,
)
def publish_schedule_week(
    organization_id: int,
    payload: SchedulePublishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    week_end = week_end_from_start(payload.week_start)
    shifts = db.scalars(
        select(ScheduleShift).where(
            and_(
                ScheduleShift.organization_id == organization_id,
                ScheduleShift.shift_date >= payload.week_start,
                ScheduleShift.shift_date <= week_end,
            )
        )
    ).all()
    if not shifts:
        raise HTTPException(status_code=404, detail="No shifts found for the selected week.")

    coverage_targets = db.scalars(
        select(ScheduleCoverageTarget).where(ScheduleCoverageTarget.organization_id == organization_id)
    ).all()
    coverage_shortages = build_coverage_shortages(shifts, list(coverage_targets))
    if coverage_shortages and not payload.force_publish:
        raise HTTPException(
            status_code=409,
            detail=f"Publish override required: {' '.join(coverage_shortages[:4])}",
        )

    published_at = datetime.utcnow()
    for shift in shifts:
        shift.is_published = True
        shift.published_at = published_at
        shift.published_by_name = current_user.full_name

    db.add(
        SchedulePublicationEvent(
            organization_id=organization_id,
            week_start=payload.week_start,
            week_end=week_end,
            action="published",
            shift_count=len(shifts),
            published_by_name=current_user.full_name,
            snapshot_data=[build_shift_snapshot(shift) for shift in shifts],
        )
    )

    db.commit()
    return SchedulePublishResponse(
        message="Schedule published successfully.",
        week_start=payload.week_start,
        week_end=week_end,
        published_shift_count=len(shifts),
    )


@app.post(
    f"{settings.api_prefix}/organizations/{{organization_id}}/schedule/unpublish",
    response_model=SchedulePublishResponse,
)
def unpublish_schedule_week(
    organization_id: int,
    payload: SchedulePublishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    week_end = week_end_from_start(payload.week_start)
    shifts = db.scalars(
        select(ScheduleShift).where(
            and_(
                ScheduleShift.organization_id == organization_id,
                ScheduleShift.shift_date >= payload.week_start,
                ScheduleShift.shift_date <= week_end,
                ScheduleShift.is_published.is_(True),
            )
        )
    ).all()
    if not shifts:
        raise HTTPException(status_code=404, detail="No published shifts found for the selected week.")

    for shift in shifts:
        shift.is_published = False

    db.add(
        SchedulePublicationEvent(
            organization_id=organization_id,
            week_start=payload.week_start,
            week_end=week_end,
            action="unpublished",
            shift_count=len(shifts),
            published_by_name=current_user.full_name,
            snapshot_data=[build_shift_snapshot(shift) for shift in shifts],
        )
    )

    db.commit()
    return SchedulePublishResponse(
        message="Schedule unpublished successfully.",
        week_start=payload.week_start,
        week_end=week_end,
        published_shift_count=len(shifts),
    )


@app.get(
    f"{settings.api_prefix}/organizations/{{organization_id}}/schedule/publications",
    response_model=list[SchedulePublicationRead],
)
def list_schedule_publications(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    events = db.scalars(
        select(SchedulePublicationEvent)
        .where(SchedulePublicationEvent.organization_id == organization_id)
        .order_by(SchedulePublicationEvent.created_at.desc())
    ).all()
    acknowledgments = db.scalars(
        select(ScheduleAcknowledgment).where(ScheduleAcknowledgment.organization_id == organization_id)
    ).all()
    ack_counts: dict[date, int] = {}
    for acknowledgment in acknowledgments:
        ack_counts[acknowledgment.week_start] = ack_counts.get(acknowledgment.week_start, 0) + 1
    return [
        SchedulePublicationRead(
            id=event.id,
            organization_id=event.organization_id,
            week_start=event.week_start,
            week_end=event.week_end,
            action=event.action,
            shift_count=event.shift_count,
            published_by_name=event.published_by_name,
            comment=event.comment,
            created_at=event.created_at,
            acknowledged_count=ack_counts.get(event.week_start, 0),
        )
        for event in events
    ]


@app.put(
    f"{settings.api_prefix}/schedule/publications/{{publication_id}}",
    response_model=SchedulePublicationRead,
)
def update_schedule_publication_comment(
    publication_id: int,
    payload: SchedulePublicationCommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    publication = get_publication_event_for_admin(publication_id, current_user, db)
    publication.comment = payload.comment
    db.commit()
    db.refresh(publication)
    ack_count = db.scalar(
        select(func.count())
        .select_from(ScheduleAcknowledgment)
        .where(
            and_(
                ScheduleAcknowledgment.organization_id == publication.organization_id,
                ScheduleAcknowledgment.week_start == publication.week_start,
            )
        )
    ) or 0
    return SchedulePublicationRead(
        id=publication.id,
        organization_id=publication.organization_id,
        week_start=publication.week_start,
        week_end=publication.week_end,
        action=publication.action,
        shift_count=publication.shift_count,
        published_by_name=publication.published_by_name,
        comment=publication.comment,
        created_at=publication.created_at,
        acknowledged_count=ack_count,
    )


@app.post(
    f"{settings.api_prefix}/schedule/publications/{{publication_id}}/restore",
    response_model=ScheduleRestoreResponse,
)
def restore_schedule_from_snapshot(
    publication_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    publication = get_publication_event_for_admin(publication_id, current_user, db)
    week_end = publication.week_end
    existing_shifts = db.scalars(
        select(ScheduleShift).where(
            and_(
                ScheduleShift.organization_id == publication.organization_id,
                ScheduleShift.shift_date >= publication.week_start,
                ScheduleShift.shift_date <= week_end,
            )
        )
    ).all()
    for shift in existing_shifts:
        db.delete(shift)
    db.flush()

    restored_count = 0
    for snapshot in publication.snapshot_data:
        db.add(
            ScheduleShift(
                organization_id=publication.organization_id,
                employee_id=int(snapshot["employee_id"]),
                shift_date=date.fromisoformat(snapshot["shift_date"]),
                start_at=datetime.fromisoformat(snapshot["start_at"]),
                end_at=datetime.fromisoformat(snapshot["end_at"]),
                location_name=snapshot.get("location_name"),
                role_label=snapshot.get("role_label"),
                is_published=False,
                published_at=snapshot.get("published_at") and datetime.fromisoformat(snapshot["published_at"]),
                published_by_name=snapshot.get("published_by_name"),
            )
        )
        restored_count += 1

    db.commit()
    return ScheduleRestoreResponse(
        message="Schedule restored from snapshot as a draft week.",
        week_start=publication.week_start,
        week_end=week_end,
        restored_shift_count=restored_count,
    )


@app.post(f"{settings.api_prefix}/schedule/acknowledgments", response_model=ScheduleAcknowledgmentRead)
def acknowledge_schedule(
    payload: ScheduleAcknowledgmentCreate,
    db: Session = Depends(get_db),
):
    employee = get_employee_or_404(payload.employee_id, payload.organization_id, db)
    acknowledgment = db.scalar(
        select(ScheduleAcknowledgment).where(
            and_(
                ScheduleAcknowledgment.organization_id == payload.organization_id,
                ScheduleAcknowledgment.employee_id == employee.id,
                ScheduleAcknowledgment.week_start == payload.week_start,
            )
        )
    )
    if acknowledgment:
        acknowledgment.acknowledged_at = datetime.utcnow()
    else:
        acknowledgment = ScheduleAcknowledgment(
            organization_id=payload.organization_id,
            employee_id=employee.id,
            week_start=payload.week_start,
        )
        db.add(acknowledgment)

    db.commit()
    db.refresh(acknowledgment)
    return acknowledgment


@app.get(
    f"{settings.api_prefix}/employees/{{employee_id}}/schedule/acknowledgments",
    response_model=list[ScheduleAcknowledgmentRead],
)
def list_schedule_acknowledgments(employee_id: int, db: Session = Depends(get_db)):
    acknowledgments = db.scalars(
        select(ScheduleAcknowledgment)
        .where(ScheduleAcknowledgment.employee_id == employee_id)
        .order_by(ScheduleAcknowledgment.acknowledged_at.desc())
    ).all()
    return list(acknowledgments)


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
        .where(
            and_(
                ScheduleShift.employee_id == employee_id,
                ScheduleShift.shift_date >= date.today(),
                ScheduleShift.is_published.is_(True),
            )
        )
        .order_by(ScheduleShift.start_at.asc())
    ).all()
    return list(shifts)


@app.get(f"{settings.api_prefix}/employees/{{employee_id}}/time-off-requests", response_model=list[TimeOffRequestRead])
def list_employee_time_off_requests(employee_id: int, db: Session = Depends(get_db)):
    requests = db.scalars(
        select(TimeOffRequest).where(TimeOffRequest.employee_id == employee_id).order_by(TimeOffRequest.created_at.desc())
    ).all()
    return list(requests)


@app.get(f"{settings.api_prefix}/employees/{{employee_id}}/shift-change-requests", response_model=list[ShiftChangeRequestRead])
def list_employee_shift_change_requests(employee_id: int, db: Session = Depends(get_db)):
    requests = db.scalars(
        select(ShiftChangeRequest)
        .where(ShiftChangeRequest.requester_employee_id == employee_id)
        .order_by(ShiftChangeRequest.created_at.desc())
    ).all()
    return [serialize_shift_change_request(request, db) for request in requests]


@app.get(f"{settings.api_prefix}/employees/{{employee_id}}/pickup-board", response_model=list[ShiftChangeRequestRead])
def list_employee_pickup_board(employee_id: int, db: Session = Depends(get_db)):
    employee = db.get(User, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")
    requests = db.scalars(
        select(ShiftChangeRequest)
        .where(
            and_(
                ShiftChangeRequest.organization_id == employee.organization_id,
                ShiftChangeRequest.request_type == ShiftChangeType.PICKUP,
                ShiftChangeRequest.status == ShiftChangeStatus.PENDING,
                ShiftChangeRequest.requester_employee_id != employee_id,
            )
        )
        .order_by(ShiftChangeRequest.created_at.desc())
    ).all()
    return [serialize_shift_change_request(request, db) for request in requests]


@app.get(
    f"{settings.api_prefix}/employees/{{employee_id}}/availability-requests",
    response_model=list[AvailabilityRequestRead],
)
def list_employee_availability_requests(employee_id: int, db: Session = Depends(get_db)):
    requests = db.scalars(
        select(EmployeeAvailabilityRequest)
        .where(EmployeeAvailabilityRequest.employee_id == employee_id)
        .order_by(EmployeeAvailabilityRequest.created_at.desc())
    ).all()
    return list(requests)


@app.post(f"{settings.api_prefix}/availability-requests", response_model=AvailabilityRequestRead)
def create_availability_request(payload: AvailabilityRequestCreate, db: Session = Depends(get_db)):
    employee = get_employee_or_404(payload.employee_id, payload.organization_id, db)
    if payload.weekday < 0 or payload.weekday > 6:
        raise HTTPException(status_code=400, detail="weekday must be between 0 and 6.")
    request = EmployeeAvailabilityRequest(
        organization_id=payload.organization_id,
        employee_id=employee.id,
        weekday=payload.weekday,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


@app.post(f"{settings.api_prefix}/shift-change-requests", response_model=ShiftChangeRequestRead)
def create_shift_change_request(payload: ShiftChangeRequestCreate, db: Session = Depends(get_db)):
    employee = get_employee_or_404(payload.requester_employee_id, payload.organization_id, db)
    shift = db.get(ScheduleShift, payload.shift_id)
    if not shift or shift.organization_id != payload.organization_id or shift.employee_id != employee.id:
        raise HTTPException(status_code=404, detail="Shift not found for this employee.")
    if shift.shift_date < date.today():
        raise HTTPException(status_code=400, detail="Only upcoming shifts can be changed.")
    existing_pending = db.scalar(
        select(ShiftChangeRequest).where(
            and_(
                ShiftChangeRequest.shift_id == payload.shift_id,
                ShiftChangeRequest.requester_employee_id == payload.requester_employee_id,
                ShiftChangeRequest.status == ShiftChangeStatus.PENDING,
            )
        )
    )
    if existing_pending:
        raise HTTPException(status_code=400, detail="A pending shift change request already exists for this shift.")

    request = ShiftChangeRequest(**payload.model_dump())
    db.add(request)
    db.commit()
    db.refresh(request)
    return serialize_shift_change_request(request, db)


@app.post(f"{settings.api_prefix}/shift-change-requests/{{request_id}}/claim", response_model=ShiftChangeRequestRead)
def claim_shift_change_request(request_id: int, payload: ShiftChangeClaimCreate, db: Session = Depends(get_db)):
    request = db.get(ShiftChangeRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Shift change request not found.")
    if request.status != ShiftChangeStatus.PENDING or request.request_type != ShiftChangeType.PICKUP:
        raise HTTPException(status_code=400, detail="This shift is not open for pickup.")
    claimant = get_employee_or_404(payload.employee_id, request.organization_id, db)
    if claimant.id == request.requester_employee_id:
        raise HTTPException(status_code=400, detail="You cannot claim your own shift.")
    request.replacement_employee_id = claimant.id
    request.manager_response = f"{claimant.full_name} offered to pick up this shift."
    db.commit()
    db.refresh(request)
    return serialize_shift_change_request(request, db)


@app.get(
    f"{settings.api_prefix}/organizations/{{organization_id}}/availability-requests",
    response_model=list[AvailabilityRequestRead],
)
def list_org_availability_requests(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    requests = db.scalars(
        select(EmployeeAvailabilityRequest)
        .where(EmployeeAvailabilityRequest.organization_id == organization_id)
        .order_by(EmployeeAvailabilityRequest.created_at.desc())
    ).all()
    return list(requests)


@app.put(f"{settings.api_prefix}/availability-requests/{{request_id}}", response_model=AvailabilityRequestRead)
def update_availability_request(
    request_id: int,
    payload: AvailabilityRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    request = db.get(EmployeeAvailabilityRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Availability request not found.")
    validate_organization_access(request.organization_id, current_user)
    request.status = payload.status
    request.manager_response = payload.manager_response
    db.commit()
    db.refresh(request)
    return request


@app.get(
    f"{settings.api_prefix}/organizations/{{organization_id}}/shift-change-requests",
    response_model=list[ShiftChangeRequestRead],
)
def list_shift_change_requests(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    requests = db.scalars(
        select(ShiftChangeRequest)
        .where(ShiftChangeRequest.organization_id == organization_id)
        .order_by(ShiftChangeRequest.created_at.desc())
    ).all()
    return [serialize_shift_change_request(request, db) for request in requests]


@app.put(f"{settings.api_prefix}/shift-change-requests/{{request_id}}", response_model=ShiftChangeRequestRead)
def update_shift_change_request(
    request_id: int,
    payload: ShiftChangeRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    request = db.get(ShiftChangeRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Shift change request not found.")
    validate_organization_access(request.organization_id, current_user)
    shift = db.get(ScheduleShift, request.shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found.")

    replacement_employee = None
    if payload.replacement_employee_id is not None:
        replacement_employee = get_employee_or_404(payload.replacement_employee_id, request.organization_id, db)

    if payload.status == ShiftChangeStatus.APPROVED:
        if replacement_employee is None:
            raise HTTPException(status_code=400, detail="Choose a replacement employee before approving.")
        shift.employee_id = replacement_employee.id
        request.replacement_employee_id = replacement_employee.id

        related_pending = db.scalars(
            select(ShiftChangeRequest).where(
                and_(
                    ShiftChangeRequest.shift_id == request.shift_id,
                    ShiftChangeRequest.status == ShiftChangeStatus.PENDING,
                    ShiftChangeRequest.id != request.id,
                )
            )
        ).all()
        for related in related_pending:
            related.status = ShiftChangeStatus.DENIED
            related.manager_response = "Another shift change request for this shift was already approved."
            related.reviewed_at = datetime.utcnow()
    elif payload.status == ShiftChangeStatus.DENIED:
        request.replacement_employee_id = payload.replacement_employee_id

    request.status = payload.status
    request.manager_response = payload.manager_response
    request.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(request)
    return serialize_shift_change_request(request, db)


@app.get(
    f"{settings.api_prefix}/organizations/{{organization_id}}/coverage-targets",
    response_model=list[CoverageTargetRead],
)
def list_coverage_targets(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    targets = db.scalars(
        select(ScheduleCoverageTarget)
        .where(ScheduleCoverageTarget.organization_id == organization_id)
        .order_by(ScheduleCoverageTarget.weekday.asc(), ScheduleCoverageTarget.daypart.asc())
    ).all()
    return list(targets)


@app.post(f"{settings.api_prefix}/coverage-targets", response_model=CoverageTargetRead)
def upsert_coverage_target(
    payload: CoverageTargetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(payload.organization_id, current_user)
    normalized_role = payload.role_label.strip() if payload.role_label else None
    target_filters = [
        ScheduleCoverageTarget.organization_id == payload.organization_id,
        ScheduleCoverageTarget.weekday == payload.weekday,
        ScheduleCoverageTarget.daypart == payload.daypart,
    ]
    target_filters.append(
        ScheduleCoverageTarget.role_label.is_(None) if normalized_role is None else ScheduleCoverageTarget.role_label == normalized_role
    )
    target = db.scalar(
        select(ScheduleCoverageTarget).where(and_(*target_filters))
    )
    if target:
        target.required_headcount = payload.required_headcount
        target.role_label = normalized_role
    else:
        target_data = payload.model_dump()
        target_data["role_label"] = normalized_role
        target = ScheduleCoverageTarget(**target_data)
        db.add(target)

    db.commit()
    db.refresh(target)
    return target


@app.post(f"{settings.api_prefix}/time-off-requests", response_model=TimeOffRequestRead)
def create_time_off_request(payload: TimeOffRequestCreate, db: Session = Depends(get_db)):
    employee = get_employee_or_404(payload.employee_id, payload.organization_id, db)
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date.")
    request = TimeOffRequest(
        organization_id=payload.organization_id,
        employee_id=employee.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


@app.get(f"{settings.api_prefix}/organizations/{{organization_id}}/time-off-requests", response_model=list[TimeOffRequestRead])
def list_org_time_off_requests(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    requests = db.scalars(
        select(TimeOffRequest).where(TimeOffRequest.organization_id == organization_id).order_by(TimeOffRequest.created_at.desc())
    ).all()
    return list(requests)


@app.put(f"{settings.api_prefix}/time-off-requests/{{request_id}}", response_model=TimeOffRequestRead)
def update_time_off_request(
    request_id: int,
    payload: TimeOffRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    request = get_time_off_request_for_admin(request_id, current_user, db)
    request.status = payload.status
    request.manager_response = payload.manager_response
    db.commit()
    db.refresh(request)
    return request


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


@app.get(
    f"{settings.api_prefix}/organizations/{{organization_id}}/integrations/quickbooks/authorize-url",
    response_model=QuickBooksAuthorizationRead,
)
def get_quickbooks_authorize_url(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    integration = db.scalar(
        select(IntegrationConnection).where(
            and_(
                IntegrationConnection.organization_id == organization_id,
                IntegrationConnection.provider == IntegrationProvider.QUICKBOOKS,
            )
        )
    )
    if not integration:
        integration = IntegrationConnection(
            organization_id=organization_id,
            provider=IntegrationProvider.QUICKBOOKS,
            status=IntegrationStatus.PENDING,
            settings={},
        )
        db.add(integration)
        db.flush()

    state = generate_state_token()
    integration.status = IntegrationStatus.PENDING
    integration.settings = {
        **(integration.settings or {}),
        "oauth_state": state,
        "oauth_redirect_uri": settings.quickbooks_redirect_uri,
    }
    db.commit()
    return QuickBooksAuthorizationRead(authorization_url=build_authorization_url(state), state=state)


@app.get(
    f"{settings.api_prefix}/organizations/{{organization_id}}/integrations/quickbooks/config-status",
    response_model=QuickBooksConfigStatus,
)
def get_quickbooks_config_status(
    organization_id: int,
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    return QuickBooksConfigStatus(
        configured=bool(settings.quickbooks_client_id and settings.quickbooks_client_secret),
        client_id_present=bool(settings.quickbooks_client_id),
        client_secret_present=bool(settings.quickbooks_client_secret),
        redirect_uri=settings.quickbooks_redirect_uri,
        environment=settings.quickbooks_environment,
        scopes=settings.quickbooks_scopes.split(),
    )


@app.get(f"{settings.api_prefix}/integrations/quickbooks/callback", response_model=QuickBooksActionResponse)
def quickbooks_callback(
    state: str,
    code: str,
    realmId: Optional[str] = None,
    db: Session = Depends(get_db),
):
    integration = db.scalar(
        select(IntegrationConnection).where(
            and_(
                IntegrationConnection.provider == IntegrationProvider.QUICKBOOKS,
                IntegrationConnection.status == IntegrationStatus.PENDING,
            )
        )
    )
    if not integration or (integration.settings or {}).get("oauth_state") != state:
        raise HTTPException(status_code=400, detail="QuickBooks OAuth state is invalid or expired.")

    tokens = exchange_code_for_tokens(code)
    integration.status = IntegrationStatus.CONNECTED
    integration.credentials_ref = seal_secret(
        {
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token"),
            "expires_at": token_expiry(tokens.get("expires_in", 3600)),
            "refresh_expires_at": token_expiry(tokens.get("x_refresh_token_expires_in", 86400)),
        }
    )
    integration.last_synced_at = datetime.utcnow()
    integration.settings = {
        **(integration.settings or {}),
        "realm_id": realmId or (integration.settings or {}).get("realm_id"),
        "company_name": (integration.settings or {}).get("company_name", "QuickBooks Company"),
        "oauth_state": None,
        "oauth_redirect_uri": settings.quickbooks_redirect_uri,
        "last_export_status": (integration.settings or {}).get("last_export_status", "ready"),
    }
    db.commit()
    db.refresh(integration)
    return QuickBooksActionResponse(
        message="QuickBooks OAuth callback completed successfully.",
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


@app.post(f"{settings.api_prefix}/integrations/{{integration_id}}/refresh", response_model=QuickBooksActionResponse)
def refresh_integration_credentials(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    integration = get_integration_for_admin(integration_id, current_user, db)
    if integration.provider != IntegrationProvider.QUICKBOOKS:
        raise HTTPException(status_code=400, detail="This refresh route is only implemented for QuickBooks.")

    tokens = unseal_secret(integration.credentials_ref)
    if not tokens or not tokens.get("refresh_token"):
        raise HTTPException(status_code=400, detail="No refresh token is stored for this QuickBooks connection.")

    refreshed = refresh_tokens(tokens["refresh_token"])
    integration.credentials_ref = seal_secret(
        {
            "access_token": refreshed["access_token"],
            "refresh_token": refreshed.get("refresh_token", tokens["refresh_token"]),
            "expires_at": token_expiry(refreshed.get("expires_in", 3600)),
            "refresh_expires_at": token_expiry(refreshed.get("x_refresh_token_expires_in", 86400)),
        }
    )
    integration.status = IntegrationStatus.CONNECTED
    integration.last_synced_at = datetime.utcnow()
    integration.settings = {
        **(integration.settings or {}),
        "last_export_status": (integration.settings or {}).get("last_export_status", "ready"),
        "token_refresh_status": "completed",
    }
    db.commit()
    db.refresh(integration)
    return QuickBooksActionResponse(
        message="QuickBooks tokens refreshed successfully.",
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
    pending_notifications = len(build_admin_notifications(organization_id, db))

    return DashboardSummary(
        organization_id=organization_id,
        active_employees=active_employees,
        currently_clocked_in=currently_clocked_in,
        report_recipients=report_recipients,
        connected_integrations=connected_integrations,
        pending_notifications=pending_notifications,
    )


@app.get(f"{settings.api_prefix}/organizations/{{organization_id}}/notifications", response_model=list[NotificationRead])
def get_admin_notifications(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    return build_admin_notifications(organization_id, db)


@app.get(f"{settings.api_prefix}/organizations/{{organization_id}}/setup-overview", response_model=SetupOverview)
def get_setup_overview(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    validate_organization_access(organization_id, current_user)
    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found.")

    admin_count = db.scalar(
        select(func.count(User.id)).where(
            and_(User.organization_id == organization_id, User.role == UserRole.ADMIN, User.is_active.is_(True))
        )
    ) or 0
    manager_count = db.scalar(
        select(func.count(User.id)).where(
            and_(User.organization_id == organization_id, User.role == UserRole.MANAGER, User.is_active.is_(True))
        )
    ) or 0
    employee_count = db.scalar(
        select(func.count(User.id)).where(
            and_(User.organization_id == organization_id, User.role == UserRole.EMPLOYEE, User.is_active.is_(True))
        )
    ) or 0
    scheduled_shift_count = db.scalar(
        select(func.count(ScheduleShift.id)).where(ScheduleShift.organization_id == organization_id)
    ) or 0
    note_count = db.scalar(select(func.count(ManagerNote.id)).where(ManagerNote.organization_id == organization_id)) or 0
    report_recipient_count = db.scalar(
        select(func.count(ReportSubscription.id)).where(
            and_(ReportSubscription.organization_id == organization_id, ReportSubscription.is_active.is_(True))
        )
    ) or 0
    time_entry_count = db.scalar(select(func.count(TimeEntry.id)).where(TimeEntry.organization_id == organization_id)) or 0
    quickbooks_connected = db.scalar(
        select(func.count(IntegrationConnection.id)).where(
            and_(
                IntegrationConnection.organization_id == organization_id,
                IntegrationConnection.provider == IntegrationProvider.QUICKBOOKS,
                IntegrationConnection.status == IntegrationStatus.CONNECTED,
            )
        )
    ) or 0

    checklist = [
        SetupChecklistItem(
            key="admin_account",
            label="Admin account ready",
            complete=admin_count > 0,
            detail=f"{admin_count} active admin account(s) found.",
        ),
        SetupChecklistItem(
            key="employees",
            label="Employees added",
            complete=employee_count > 0,
            detail=f"{employee_count} active employee account(s) found.",
        ),
        SetupChecklistItem(
            key="schedules",
            label="Schedules created",
            complete=scheduled_shift_count > 0,
            detail=f"{scheduled_shift_count} scheduled shift(s) found.",
        ),
        SetupChecklistItem(
            key="manager_notes",
            label="Manager notes configured",
            complete=note_count > 0,
            detail=f"{note_count} manager note(s) found.",
        ),
        SetupChecklistItem(
            key="reports",
            label="Report recipients added",
            complete=report_recipient_count > 0,
            detail=f"{report_recipient_count} report recipient(s) found.",
        ),
        SetupChecklistItem(
            key="quickbooks_config",
            label="QuickBooks credentials loaded",
            complete=bool(settings.quickbooks_client_id and settings.quickbooks_client_secret),
            detail=(
                "Client ID and secret are loaded from environment."
                if settings.quickbooks_client_id and settings.quickbooks_client_secret
                else "Add QuickBooks credentials to .env to enable live OAuth."
            ),
        ),
        SetupChecklistItem(
            key="quickbooks_connection",
            label="QuickBooks connected",
            complete=bool(quickbooks_connected),
            detail=(
                "QuickBooks is connected and ready for exports."
                if quickbooks_connected
                else "Connect QuickBooks from the Integrations tab."
            ),
        ),
        SetupChecklistItem(
            key="time_clock_usage",
            label="Time clock activity recorded",
            complete=time_entry_count > 0,
            detail=f"{time_entry_count} time entry record(s) found.",
        ),
    ]

    return SetupOverview(
        organization_id=organization_id,
        organization_name=organization.name,
        timezone=organization.timezone,
        admin_count=admin_count,
        manager_count=manager_count,
        employee_count=employee_count,
        scheduled_shift_count=scheduled_shift_count,
        note_count=note_count,
        report_recipient_count=report_recipient_count,
        time_entry_count=time_entry_count,
        quickbooks_configured=bool(settings.quickbooks_client_id and settings.quickbooks_client_secret),
        quickbooks_connected=bool(quickbooks_connected),
        checklist=checklist,
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
        existing_shifts = db.scalars(select(ScheduleShift).where(ScheduleShift.organization_id == existing_org.id)).all()
        for shift in existing_shifts:
            shift.is_published = True
            shift.published_at = shift.published_at or datetime.utcnow()
            shift.published_by_name = shift.published_by_name or "Alex Owner"
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
                is_published=True,
                published_at=datetime.utcnow(),
                published_by_name="Alex Owner",
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
