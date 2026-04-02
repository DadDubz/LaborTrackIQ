import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TEMP_DIR.name) / 'test.db'}"
os.environ["SECRET_KEY"] = "labortrackiq-test-secret"

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import Base, engine
from app.main import app, ensure_schedule_shift_publish_columns, reset_rate_limit_state
from app.models import (
    EmployeeProfile,
    IntegrationConnection,
    IntegrationProvider,
    IntegrationStatus,
    Organization,
    ScheduleShift,
    ShiftChangeRequest,
    ShiftChangeType,
    TimeEntry,
    User,
    UserRole,
)
from app.security import create_access_token
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class LaborTrackIQSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        _TEMP_DIR.cleanup()

    def setUp(self):
        reset_rate_limit_state()
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        ensure_schedule_shift_publish_columns()
        response = self.client.post("/api/bootstrap/demo")
        self.assertEqual(response.status_code, 200, response.text)

    def admin_headers(self):
        response = self.client.post(
            "/api/auth/login",
            json={
                "organization_id": 1,
                "email": "admin@demodiner.com",
                "password": "admin1234",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def employee_headers(self, employee_number="1001", pin_code="1234"):
        return {
            "X-Employee-Number": employee_number,
            "X-Employee-Pin": pin_code,
        }

    def get_week_start(self, day: date) -> date:
        return day - timedelta(days=day.weekday())

    def test_employee_self_service_requires_headers(self):
        unauthorized = self.client.get("/api/employees/3/profile")
        self.assertEqual(unauthorized.status_code, 401, unauthorized.text)

        authorized = self.client.get("/api/employees/3/profile", headers=self.employee_headers())
        self.assertEqual(authorized.status_code, 200, authorized.text)
        self.assertEqual(authorized.json()["employee_number"], "1001")

    def test_database_health_endpoint_reports_connected(self):
        response = self.client.get("/health/db")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["database"], "connected")

    def test_readiness_endpoint_reports_ready_in_local_mode(self):
        response = self.client.get("/health/ready")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "ready")

    def test_readiness_endpoint_reports_not_ready_for_bad_production_config(self):
        original_environment = settings.app_environment
        original_secret = settings.secret_key
        original_bootstrap = settings.allow_demo_bootstrap
        original_database_url = settings.database_url
        try:
            settings.app_environment = "production"
            settings.secret_key = "labortrackiq-dev-secret"
            settings.allow_demo_bootstrap = True
            settings.database_url = "sqlite:///tmp/test.db"

            response = self.client.get("/health/ready")
            self.assertEqual(response.status_code, 503, response.text)
            issues = response.json()["detail"]["issues"]
            self.assertIn("default_secret_key", issues)
            self.assertIn("demo_bootstrap_enabled", issues)
            self.assertIn("sqlite_in_production", issues)
        finally:
            settings.app_environment = original_environment
            settings.secret_key = original_secret
            settings.allow_demo_bootstrap = original_bootstrap
            settings.database_url = original_database_url

    def test_request_payload_too_large_is_rejected(self):
        headers = self.admin_headers()
        oversized_body = "x" * (settings.max_request_bytes + 1)
        response = self.client.post(
            "/api/notes",
            headers=headers,
            json={
                "organization_id": 1,
                "employee_id": None,
                "title": "Oversized payload",
                "body": oversized_body,
                "is_active": True,
                "show_at_clock_in": True,
            },
        )
        self.assertEqual(response.status_code, 413, response.text)

    def test_login_rate_limit_returns_429_when_exceeded(self):
        original_limit = settings.auth_rate_limit
        original_window = settings.auth_rate_window_seconds
        original_account_limit = settings.auth_account_rate_limit
        original_account_window = settings.auth_account_rate_window_seconds
        original_trust_proxy_headers = settings.trust_proxy_headers
        try:
            settings.auth_rate_limit = 2
            settings.auth_rate_window_seconds = 60
            settings.auth_account_rate_limit = 100
            settings.auth_account_rate_window_seconds = 60
            settings.trust_proxy_headers = False
            reset_rate_limit_state()

            for _ in range(2):
                response = self.client.post(
                    "/api/auth/login",
                    json={
                        "organization_id": 1,
                        "email": "admin@demodiner.com",
                        "password": "wrong-password",
                    },
                )
                self.assertEqual(response.status_code, 401, response.text)

            blocked = self.client.post(
                "/api/auth/login",
                json={
                    "organization_id": 1,
                    "email": "admin@demodiner.com",
                    "password": "wrong-password",
                },
            )
            self.assertEqual(blocked.status_code, 429, blocked.text)
        finally:
            settings.auth_rate_limit = original_limit
            settings.auth_rate_window_seconds = original_window
            settings.auth_account_rate_limit = original_account_limit
            settings.auth_account_rate_window_seconds = original_account_window
            settings.trust_proxy_headers = original_trust_proxy_headers
            reset_rate_limit_state()

    def test_login_rate_limit_ignores_forwarded_for_when_proxy_headers_untrusted(self):
        original_limit = settings.auth_rate_limit
        original_window = settings.auth_rate_window_seconds
        original_account_limit = settings.auth_account_rate_limit
        original_account_window = settings.auth_account_rate_window_seconds
        original_trust_proxy_headers = settings.trust_proxy_headers
        try:
            settings.auth_rate_limit = 1
            settings.auth_rate_window_seconds = 60
            settings.auth_account_rate_limit = 100
            settings.auth_account_rate_window_seconds = 60
            settings.trust_proxy_headers = False
            reset_rate_limit_state()

            first = self.client.post(
                "/api/auth/login",
                headers={"X-Forwarded-For": "10.0.0.1"},
                json={
                    "organization_id": 1,
                    "email": "admin@demodiner.com",
                    "password": "wrong-password",
                },
            )
            self.assertEqual(first.status_code, 401, first.text)

            second = self.client.post(
                "/api/auth/login",
                headers={"X-Forwarded-For": "10.0.0.2"},
                json={
                    "organization_id": 1,
                    "email": "admin@demodiner.com",
                    "password": "wrong-password",
                },
            )
            self.assertEqual(second.status_code, 429, second.text)
        finally:
            settings.auth_rate_limit = original_limit
            settings.auth_rate_window_seconds = original_window
            settings.auth_account_rate_limit = original_account_limit
            settings.auth_account_rate_window_seconds = original_account_window
            settings.trust_proxy_headers = original_trust_proxy_headers
            reset_rate_limit_state()

    def test_login_rate_limit_uses_forwarded_for_when_proxy_headers_trusted(self):
        original_limit = settings.auth_rate_limit
        original_window = settings.auth_rate_window_seconds
        original_account_limit = settings.auth_account_rate_limit
        original_account_window = settings.auth_account_rate_window_seconds
        original_trust_proxy_headers = settings.trust_proxy_headers
        try:
            settings.auth_rate_limit = 1
            settings.auth_rate_window_seconds = 60
            settings.auth_account_rate_limit = 100
            settings.auth_account_rate_window_seconds = 60
            settings.trust_proxy_headers = True
            reset_rate_limit_state()

            first = self.client.post(
                "/api/auth/login",
                headers={"X-Forwarded-For": "10.0.0.1"},
                json={
                    "organization_id": 1,
                    "email": "admin@demodiner.com",
                    "password": "wrong-password",
                },
            )
            self.assertEqual(first.status_code, 401, first.text)

            second = self.client.post(
                "/api/auth/login",
                headers={"X-Forwarded-For": "10.0.0.2"},
                json={
                    "organization_id": 1,
                    "email": "admin@demodiner.com",
                    "password": "wrong-password",
                },
            )
            self.assertEqual(second.status_code, 401, second.text)
        finally:
            settings.auth_rate_limit = original_limit
            settings.auth_rate_window_seconds = original_window
            settings.auth_account_rate_limit = original_account_limit
            settings.auth_account_rate_window_seconds = original_account_window
            settings.trust_proxy_headers = original_trust_proxy_headers
            reset_rate_limit_state()

    def test_login_account_rate_limit_applies_across_sources(self):
        original_limit = settings.auth_rate_limit
        original_window = settings.auth_rate_window_seconds
        original_account_limit = settings.auth_account_rate_limit
        original_account_window = settings.auth_account_rate_window_seconds
        original_trust_proxy_headers = settings.trust_proxy_headers
        try:
            settings.auth_rate_limit = 100
            settings.auth_rate_window_seconds = 60
            settings.auth_account_rate_limit = 2
            settings.auth_account_rate_window_seconds = 60
            settings.trust_proxy_headers = True
            reset_rate_limit_state()

            first = self.client.post(
                "/api/auth/login",
                headers={"X-Forwarded-For": "10.0.0.1"},
                json={
                    "organization_id": 1,
                    "email": "admin@demodiner.com",
                    "password": "wrong-password",
                },
            )
            self.assertEqual(first.status_code, 401, first.text)

            second = self.client.post(
                "/api/auth/login",
                headers={"X-Forwarded-For": "10.0.0.2"},
                json={
                    "organization_id": 1,
                    "email": "admin@demodiner.com",
                    "password": "wrong-password",
                },
            )
            self.assertEqual(second.status_code, 401, second.text)

            blocked = self.client.post(
                "/api/auth/login",
                headers={"X-Forwarded-For": "10.0.0.3"},
                json={
                    "organization_id": 1,
                    "email": "admin@demodiner.com",
                    "password": "wrong-password",
                },
            )
            self.assertEqual(blocked.status_code, 429, blocked.text)
        finally:
            settings.auth_rate_limit = original_limit
            settings.auth_rate_window_seconds = original_window
            settings.auth_account_rate_limit = original_account_limit
            settings.auth_account_rate_window_seconds = original_account_window
            settings.trust_proxy_headers = original_trust_proxy_headers
            reset_rate_limit_state()

    def test_login_accepts_email_case_insensitively(self):
        response = self.client.post(
            "/api/auth/login",
            json={
                "organization_id": 1,
                "email": "ADMIN@DEMODINER.COM",
                "password": "admin1234",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_protected_endpoint_rejects_token_organization_mismatch(self):
        mismatch_token = create_access_token(user_id=1, organization_id=9999, role="admin")
        response = self.client.get("/api/organizations/1/users", headers={"Authorization": f"Bearer {mismatch_token}"})
        self.assertEqual(response.status_code, 401, response.text)

    def test_clock_lookup_rate_limit_returns_429_when_exceeded(self):
        original_limit = settings.clock_rate_limit
        original_window = settings.clock_rate_window_seconds
        original_employee_limit = settings.clock_employee_rate_limit
        original_employee_window = settings.clock_employee_rate_window_seconds
        try:
            settings.clock_rate_limit = 2
            settings.clock_rate_window_seconds = 60
            settings.clock_employee_rate_limit = 100
            settings.clock_employee_rate_window_seconds = 60
            reset_rate_limit_state()

            payload = {
                "organization_id": 1,
                "employee_number": "1001",
                "pin_code": "1234",
                "source": "test-suite",
            }
            for _ in range(2):
                ok = self.client.post("/api/clock/lookup", json=payload)
                self.assertEqual(ok.status_code, 200, ok.text)

            blocked = self.client.post("/api/clock/lookup", json=payload)
            self.assertEqual(blocked.status_code, 429, blocked.text)
        finally:
            settings.clock_rate_limit = original_limit
            settings.clock_rate_window_seconds = original_window
            settings.clock_employee_rate_limit = original_employee_limit
            settings.clock_employee_rate_window_seconds = original_employee_window
            reset_rate_limit_state()

    def test_clock_employee_rate_limit_applies_across_sources(self):
        original_limit = settings.clock_rate_limit
        original_window = settings.clock_rate_window_seconds
        original_employee_limit = settings.clock_employee_rate_limit
        original_employee_window = settings.clock_employee_rate_window_seconds
        try:
            settings.clock_rate_limit = 100
            settings.clock_rate_window_seconds = 60
            settings.clock_employee_rate_limit = 2
            settings.clock_employee_rate_window_seconds = 60
            reset_rate_limit_state()

            payload = {
                "organization_id": 1,
                "employee_number": "1001",
                "pin_code": "1234",
                "source": "test-suite",
            }

            first = self.client.post("/api/clock/lookup", headers={"X-Forwarded-For": "10.0.0.1"}, json=payload)
            self.assertEqual(first.status_code, 200, first.text)
            second = self.client.post("/api/clock/lookup", headers={"X-Forwarded-For": "10.0.0.2"}, json=payload)
            self.assertEqual(second.status_code, 200, second.text)
            blocked = self.client.post("/api/clock/lookup", headers={"X-Forwarded-For": "10.0.0.3"}, json=payload)
            self.assertEqual(blocked.status_code, 429, blocked.text)
        finally:
            settings.clock_rate_limit = original_limit
            settings.clock_rate_window_seconds = original_window
            settings.clock_employee_rate_limit = original_employee_limit
            settings.clock_employee_rate_window_seconds = original_employee_window
            reset_rate_limit_state()

    def test_duplicate_employee_identity_is_rejected(self):
        headers = self.admin_headers()

        duplicate_employee_number = self.client.post(
            "/api/users",
            headers=headers,
            json={
                "organization_id": 1,
                "full_name": "Duplicate Employee",
                "email": "duplicate.employee@demodiner.com",
                "role": "employee",
                "employee_number": "1001",
                "pin_code": "9999",
                "job_title": "Cashier",
            },
        )
        self.assertEqual(duplicate_employee_number.status_code, 400, duplicate_employee_number.text)

        duplicate_email = self.client.post(
            "/api/users",
            headers=headers,
            json={
                "organization_id": 1,
                "full_name": "Duplicate Manager",
                "email": "ADMIN@DEMODINER.COM",
                "role": "manager",
                "password": "secret123",
            },
        )
        self.assertEqual(duplicate_email.status_code, 400, duplicate_email.text)

    def test_employee_identifier_validation_rejects_invalid_formats(self):
        headers = self.admin_headers()
        invalid_employee_number = self.client.post(
            "/api/users",
            headers=headers,
            json={
                "organization_id": 1,
                "full_name": "Invalid Employee Number",
                "email": "invalid.employee.number@demodiner.com",
                "role": "employee",
                "employee_number": "1001!",
                "pin_code": "1234",
                "job_title": "Cashier",
            },
        )
        self.assertEqual(invalid_employee_number.status_code, 422, invalid_employee_number.text)

        invalid_pin = self.client.post(
            "/api/clock/lookup",
            json={
                "organization_id": 1,
                "employee_number": "1001",
                "pin_code": "12ab",
                "source": "test-suite",
            },
        )
        self.assertEqual(invalid_pin.status_code, 422, invalid_pin.text)

    def test_admin_user_password_validation_rejects_short_values(self):
        headers = self.admin_headers()
        short_password = self.client.post(
            "/api/users",
            headers=headers,
            json={
                "organization_id": 1,
                "full_name": "Short Password Manager",
                "email": "short.password.manager@demodiner.com",
                "role": "manager",
                "password": "short7",
            },
        )
        self.assertEqual(short_password.status_code, 422, short_password.text)

    def test_admin_audit_events_capture_user_creation(self):
        headers = self.admin_headers()
        created = self.client.post(
            "/api/users",
            headers=headers,
            json={
                "organization_id": 1,
                "full_name": "Audit Employee",
                "email": "audit.employee@demodiner.com",
                "role": "employee",
                "employee_number": "1008",
                "pin_code": "1111",
                "job_title": "Audit Role",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        created_user_id = created.json()["id"]

        events = self.client.get("/api/organizations/1/audit-events", headers=headers)
        self.assertEqual(events.status_code, 200, events.text)
        actions = [event["action"] for event in events.json()]
        self.assertIn("user_created", actions)
        matching = [event for event in events.json() if event["action"] == "user_created" and event["entity_id"] == created_user_id]
        self.assertTrue(matching)

    def test_employee_pin_is_not_stored_plaintext(self):
        with Session(engine) as db:
            profile = db.scalar(select(EmployeeProfile).where(EmployeeProfile.employee_number == "1001"))
            self.assertIsNotNone(profile)
            self.assertTrue(bool(profile.pin_hash))
            self.assertNotEqual(profile.pin_code, "1234")

    def test_malformed_pin_hash_fails_closed(self):
        with Session(engine) as db:
            profile = db.scalar(select(EmployeeProfile).where(EmployeeProfile.employee_number == "1001"))
            self.assertIsNotNone(profile)
            profile.pin_hash = "malformed-hash"
            db.add(profile)
            db.commit()

        response = self.client.post(
            "/api/clock/lookup",
            json={
                "organization_id": 1,
                "employee_number": "1001",
                "pin_code": "1234",
                "source": "test-suite",
            },
        )
        self.assertEqual(response.status_code, 404, response.text)

    def test_open_time_entry_unique_per_employee(self):
        with Session(engine) as db:
            first = db.scalar(
                select(EmployeeProfile).where(EmployeeProfile.employee_number == "1001")
            )
            self.assertIsNotNone(first)
            employee_id = first.user_id
            db.add_all(
                [
                    TimeEntry(
                        organization_id=1,
                        employee_id=employee_id,
                        clock_in_at=datetime.utcnow(),
                        clock_in_source="test-suite",
                    ),
                    TimeEntry(
                        organization_id=1,
                        employee_id=employee_id,
                        clock_in_at=datetime.utcnow() + timedelta(minutes=1),
                        clock_in_source="test-suite",
                    ),
                ]
            )
            with self.assertRaises(IntegrityError):
                db.commit()

    def test_pending_shift_change_unique_per_shift_and_requester(self):
        shift_day = date.today() + timedelta(days=2)
        shift_start = datetime.combine(shift_day, datetime.min.time()).replace(hour=9)
        shift_end = datetime.combine(shift_day, datetime.min.time()).replace(hour=17)
        with Session(engine) as db:
            db.add(
                ScheduleShift(
                    organization_id=1,
                    employee_id=3,
                    shift_date=shift_day,
                    start_at=shift_start,
                    end_at=shift_end,
                    location_name="Main Store",
                    role_label="Front Counter",
                    is_published=False,
                )
            )
            db.commit()
            shift = db.scalar(
                select(ScheduleShift).where(
                    ScheduleShift.organization_id == 1,
                    ScheduleShift.employee_id == 3,
                    ScheduleShift.shift_date == shift_day,
                )
            )
            self.assertIsNotNone(shift)
            db.add_all(
                [
                    ShiftChangeRequest(
                        organization_id=1,
                        shift_id=shift.id,
                        requester_employee_id=3,
                        request_type=ShiftChangeType.PICKUP,
                        note="First request",
                    ),
                    ShiftChangeRequest(
                        organization_id=1,
                        shift_id=shift.id,
                        requester_employee_id=3,
                        request_type=ShiftChangeType.PICKUP,
                        note="Duplicate pending request",
                    ),
                ]
            )
            with self.assertRaises(IntegrityError):
                db.commit()

    def test_report_recipient_duplicate_and_restore_flow(self):
        headers = self.admin_headers()
        payload = {
            "organization_id": 1,
            "email": "ops@example.com",
            "report_type": "daily_labor_summary",
        }

        first = self.client.post("/api/report-recipients", headers=headers, json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        first_id = first.json()["id"]

        duplicate = self.client.post("/api/report-recipients", headers=headers, json=payload)
        self.assertEqual(duplicate.status_code, 400, duplicate.text)

        archived = self.client.delete(f"/api/report-recipients/{first_id}", headers=headers)
        self.assertEqual(archived.status_code, 200, archived.text)

        restored = self.client.post("/api/report-recipients", headers=headers, json=payload)
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(restored.json()["id"], first_id)

    def test_integration_create_is_idempotent_per_provider(self):
        headers = self.admin_headers()
        first = self.client.post(
            "/api/integrations",
            headers=headers,
            json={
                "organization_id": 1,
                "provider": "xero",
                "status": "pending",
                "settings": {"mode": "initial"},
            },
        )
        self.assertEqual(first.status_code, 200, first.text)
        first_id = first.json()["id"]

        second = self.client.post(
            "/api/integrations",
            headers=headers,
            json={
                "organization_id": 1,
                "provider": "xero",
                "status": "connected",
                "settings": {"mode": "updated"},
            },
        )
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["id"], first_id)
        self.assertEqual(second.json()["status"], "connected")

        integrations = self.client.get("/api/organizations/1/integrations", headers=headers)
        self.assertEqual(integrations.status_code, 200, integrations.text)
        xero_integrations = [item for item in integrations.json() if item["provider"] == "xero"]
        self.assertEqual(len(xero_integrations), 1)

    def test_schedule_acknowledgment_is_idempotent_per_week(self):
        week_start = self.get_week_start(date.today()).isoformat()
        payload = {
            "organization_id": 1,
            "employee_id": 3,
            "week_start": week_start,
        }
        first = self.client.post("/api/schedule/acknowledgments", headers=self.employee_headers(), json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        first_id = first.json()["id"]

        second = self.client.post("/api/schedule/acknowledgments", headers=self.employee_headers(), json=payload)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["id"], first_id)

        acknowledgments = self.client.get("/api/employees/3/schedule/acknowledgments", headers=self.employee_headers())
        self.assertEqual(acknowledgments.status_code, 200, acknowledgments.text)
        matching = [item for item in acknowledgments.json() if item["week_start"] == week_start]
        self.assertEqual(len(matching), 1)

    def test_coverage_target_upsert_is_idempotent(self):
        headers = self.admin_headers()
        payload = {
            "organization_id": 1,
            "weekday": 2,
            "daypart": "lunch",
            "role_label": "Front Counter",
            "required_headcount": 2,
        }
        first = self.client.post("/api/coverage-targets", headers=headers, json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        target_id = first.json()["id"]

        payload["required_headcount"] = 4
        second = self.client.post("/api/coverage-targets", headers=headers, json=payload)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["id"], target_id)
        self.assertEqual(second.json()["required_headcount"], 4)

        listing = self.client.get("/api/organizations/1/coverage-targets", headers=headers)
        self.assertEqual(listing.status_code, 200, listing.text)
        matches = [
            item
            for item in listing.json()
            if item["weekday"] == 2 and item["daypart"] == "lunch" and item["role_label"] == "Front Counter"
        ]
        self.assertEqual(len(matches), 1)

    def test_quickbooks_export_includes_only_approved_closed_entries(self):
        headers = self.admin_headers()

        first_clock_in = self.client.post(
            "/api/clock/in-out",
            json={
                "organization_id": 1,
                "employee_number": "1001",
                "pin_code": "1234",
                "source": "test-suite",
            },
        )
        self.assertEqual(first_clock_in.status_code, 200, first_clock_in.text)
        first_clock_out = self.client.post(
            "/api/clock/in-out",
            json={
                "organization_id": 1,
                "employee_number": "1001",
                "pin_code": "1234",
                "source": "test-suite",
            },
        )
        self.assertEqual(first_clock_out.status_code, 200, first_clock_out.text)

        list_entries = self.client.get("/api/organizations/1/time-entries", headers=headers)
        self.assertEqual(list_entries.status_code, 200, list_entries.text)
        first_entry_id = list_entries.json()[0]["id"]

        approve_entry = self.client.put(
            f"/api/time-entries/{first_entry_id}",
            headers=headers,
            json={
                "approved": True,
                "notes": "Approved for export",
                "clock_out_at": list_entries.json()[0]["clock_out_at"],
            },
        )
        self.assertEqual(approve_entry.status_code, 200, approve_entry.text)

        second_clock_in = self.client.post(
            "/api/clock/in-out",
            json={
                "organization_id": 1,
                "employee_number": "1001",
                "pin_code": "1234",
                "source": "test-suite",
            },
        )
        self.assertEqual(second_clock_in.status_code, 200, second_clock_in.text)
        second_clock_out = self.client.post(
            "/api/clock/in-out",
            json={
                "organization_id": 1,
                "employee_number": "1001",
                "pin_code": "1234",
                "source": "test-suite",
            },
        )
        self.assertEqual(second_clock_out.status_code, 200, second_clock_out.text)

        connect = self.client.post(
            "/api/organizations/1/integrations/quickbooks/connect",
            headers=headers,
            json={
                "organization_id": 1,
                "company_name": "Demo Diner Books",
                "realm_id": "realm-1",
            },
        )
        self.assertEqual(connect.status_code, 200, connect.text)
        integration_id = connect.json()["integration"]["id"]

        export = self.client.post(
            f"/api/integrations/{integration_id}/export-labor",
            headers=headers,
            json={
                "start_date": (date.today() - timedelta(days=1)).isoformat(),
                "end_date": (date.today() + timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(export.status_code, 200, export.text)
        summary = export.json()["export_summary"]
        self.assertEqual(summary["entries"], 1)

    def test_quickbooks_callback_matches_pending_connection_by_state(self):
        with Session(engine) as db:
            org_one_integration = db.scalar(
                select(IntegrationConnection).where(
                    IntegrationConnection.organization_id == 1,
                    IntegrationConnection.provider == IntegrationProvider.QUICKBOOKS,
                )
            )
            self.assertIsNotNone(org_one_integration)
            org_one_integration.status = IntegrationStatus.PENDING
            org_one_integration.settings = {
                "oauth_state": "state-org-one",
                "oauth_state_issued_at": datetime.utcnow().isoformat(),
            }
            org_one_integration.credentials_ref = None
            db.add(org_one_integration)

            org_two = Organization(name="Demo Org Two", timezone="America/Chicago")
            db.add(org_two)
            db.flush()
            db.add(
                User(
                    organization_id=org_two.id,
                    full_name="Org Two Admin",
                    email="org.two.admin@example.com",
                    role=UserRole.ADMIN,
                    password_hash="not-used-in-this-test",
                )
            )
            org_two_integration = IntegrationConnection(
                organization_id=org_two.id,
                provider=IntegrationProvider.QUICKBOOKS,
                status=IntegrationStatus.PENDING,
                settings={
                    "oauth_state": "state-org-two",
                    "oauth_state_issued_at": datetime.utcnow().isoformat(),
                    "company_name": "Org Two Co",
                },
            )
            db.add(org_two_integration)
            db.commit()
            org_one_integration_id = org_one_integration.id
            org_two_integration_id = org_two_integration.id
            org_two_id = org_two.id

        with patch(
            "app.main.exchange_code_for_tokens",
            return_value={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 3600,
                "x_refresh_token_expires_in": 86400,
            },
        ):
            callback = self.client.get(
                "/api/integrations/quickbooks/callback",
                params={"state": "state-org-two", "code": "demo-code", "realmId": "realm-two"},
            )
        self.assertEqual(callback.status_code, 200, callback.text)
        self.assertEqual(callback.json()["integration"]["id"], org_two_integration_id)
        self.assertEqual(callback.json()["integration"]["organization_id"], org_two_id)

        with Session(engine) as db:
            org_one_refreshed = db.get(IntegrationConnection, org_one_integration_id)
            org_two_refreshed = db.get(IntegrationConnection, org_two_integration_id)
            self.assertEqual(org_one_refreshed.status, IntegrationStatus.PENDING)
            self.assertEqual(org_two_refreshed.status, IntegrationStatus.CONNECTED)

    def test_quickbooks_callback_rejects_expired_oauth_state(self):
        with Session(engine) as db:
            integration = db.scalar(
                select(IntegrationConnection).where(
                    IntegrationConnection.organization_id == 1,
                    IntegrationConnection.provider == IntegrationProvider.QUICKBOOKS,
                )
            )
            self.assertIsNotNone(integration)
            integration.status = IntegrationStatus.PENDING
            integration.settings = {
                "oauth_state": "expired-state",
                "oauth_state_issued_at": "2000-01-01T00:00:00",
            }
            integration.credentials_ref = None
            db.add(integration)
            db.commit()
            integration_id = integration.id

        callback = self.client.get(
            "/api/integrations/quickbooks/callback",
            params={"state": "expired-state", "code": "demo-code", "realmId": "realm-one"},
        )
        self.assertEqual(callback.status_code, 400, callback.text)

        with Session(engine) as db:
            refreshed = db.get(IntegrationConnection, integration_id)
            self.assertEqual(refreshed.status, IntegrationStatus.ERROR)
            self.assertIsNone((refreshed.settings or {}).get("oauth_state"))

    def test_schedule_publish_and_unpublish_controls_employee_visibility(self):
        headers = self.admin_headers()
        shift_day = date.today() + timedelta(days=2)
        shift_start = datetime.combine(shift_day, datetime.min.time()).replace(hour=9).isoformat() + "Z"
        shift_end = datetime.combine(shift_day, datetime.min.time()).replace(hour=17).isoformat() + "Z"

        created_shift = self.client.post(
            "/api/shifts",
            headers=headers,
            json={
                "organization_id": 1,
                "employee_id": 3,
                "shift_date": shift_day.isoformat(),
                "start_at": shift_start,
                "end_at": shift_end,
                "location_name": "Main Store",
                "role_label": "Front Counter",
            },
        )
        self.assertEqual(created_shift.status_code, 200, created_shift.text)
        shift_id = created_shift.json()["id"]

        before_publish = self.client.get("/api/employees/3/schedule", headers=self.employee_headers())
        self.assertEqual(before_publish.status_code, 200, before_publish.text)
        self.assertNotIn(shift_id, [shift["id"] for shift in before_publish.json()])

        week_start = self.get_week_start(shift_day)
        publish = self.client.post(
            "/api/organizations/1/schedule/publish",
            headers=headers,
            json={"week_start": week_start.isoformat(), "force_publish": False},
        )
        self.assertEqual(publish.status_code, 200, publish.text)

        after_publish = self.client.get("/api/employees/3/schedule", headers=self.employee_headers())
        self.assertEqual(after_publish.status_code, 200, after_publish.text)
        self.assertIn(shift_id, [shift["id"] for shift in after_publish.json()])

        unpublish = self.client.post(
            "/api/organizations/1/schedule/unpublish",
            headers=headers,
            json={"week_start": week_start.isoformat(), "force_publish": False},
        )
        self.assertEqual(unpublish.status_code, 200, unpublish.text)

        after_unpublish = self.client.get("/api/employees/3/schedule", headers=self.employee_headers())
        self.assertEqual(after_unpublish.status_code, 200, after_unpublish.text)
        self.assertNotIn(shift_id, [shift["id"] for shift in after_unpublish.json()])

    def test_shift_change_approval_enforces_pending_and_replacement_rules(self):
        headers = self.admin_headers()

        new_employee = self.client.post(
            "/api/users",
            headers=headers,
            json={
                "organization_id": 1,
                "full_name": "Coverage Employee",
                "email": "coverage.employee@demodiner.com",
                "role": "employee",
                "employee_number": "1003",
                "pin_code": "2468",
                "job_title": "Coverage",
            },
        )
        self.assertEqual(new_employee.status_code, 200, new_employee.text)
        replacement_employee_id = new_employee.json()["id"]

        shift_day = date.today() + timedelta(days=3)
        shift_start = datetime.combine(shift_day, datetime.min.time()).replace(hour=10).isoformat() + "Z"
        shift_end = datetime.combine(shift_day, datetime.min.time()).replace(hour=16).isoformat() + "Z"
        created_shift = self.client.post(
            "/api/shifts",
            headers=headers,
            json={
                "organization_id": 1,
                "employee_id": 3,
                "shift_date": shift_day.isoformat(),
                "start_at": shift_start,
                "end_at": shift_end,
                "location_name": "Main Store",
                "role_label": "Front Counter",
            },
        )
        self.assertEqual(created_shift.status_code, 200, created_shift.text)
        shift_id = created_shift.json()["id"]

        shift_change = self.client.post(
            "/api/shift-change-requests",
            headers=self.employee_headers(),
            json={
                "organization_id": 1,
                "shift_id": shift_id,
                "requester_employee_id": 3,
                "request_type": "pickup",
                "note": "Need this shift covered",
            },
        )
        self.assertEqual(shift_change.status_code, 200, shift_change.text)
        request_id = shift_change.json()["id"]

        requester_as_replacement = self.client.put(
            f"/api/shift-change-requests/{request_id}",
            headers=headers,
            json={
                "status": "approved",
                "manager_response": "Should fail",
                "replacement_employee_id": 3,
            },
        )
        self.assertEqual(requester_as_replacement.status_code, 400, requester_as_replacement.text)

        approve = self.client.put(
            f"/api/shift-change-requests/{request_id}",
            headers=headers,
            json={
                "status": "approved",
                "manager_response": "Approved coverage",
                "replacement_employee_id": replacement_employee_id,
            },
        )
        self.assertEqual(approve.status_code, 200, approve.text)

        second_approval = self.client.put(
            f"/api/shift-change-requests/{request_id}",
            headers=headers,
            json={
                "status": "approved",
                "manager_response": "Should not allow re-approval",
                "replacement_employee_id": replacement_employee_id,
            },
        )
        self.assertEqual(second_approval.status_code, 400, second_approval.text)

    def test_bootstrap_can_be_disabled_for_non_local_environments(self):
        original_value = settings.allow_demo_bootstrap
        settings.allow_demo_bootstrap = False
        try:
            response = self.client.post("/api/bootstrap/demo")
            self.assertEqual(response.status_code, 403, response.text)
        finally:
            settings.allow_demo_bootstrap = original_value

    def test_shift_date_must_match_start_and_end_datetimes(self):
        headers = self.admin_headers()
        shift_day = date.today() + timedelta(days=4)
        mismatched_start = datetime.combine(shift_day, datetime.min.time()).replace(hour=9).isoformat() + "Z"
        mismatched_end = datetime.combine(shift_day + timedelta(days=1), datetime.min.time()).replace(hour=17).isoformat() + "Z"

        response = self.client.post(
            "/api/shifts",
            headers=headers,
            json={
                "organization_id": 1,
                "employee_id": 3,
                "shift_date": shift_day.isoformat(),
                "start_at": mismatched_start,
                "end_at": mismatched_end,
                "location_name": "Main Store",
                "role_label": "Front Counter",
            },
        )
        self.assertEqual(response.status_code, 400, response.text)


if __name__ == "__main__":
    unittest.main()
