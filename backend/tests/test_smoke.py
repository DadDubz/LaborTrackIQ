import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path


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
from app.main import app, ensure_schedule_shift_publish_columns


class LaborTrackIQSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        _TEMP_DIR.cleanup()

    def setUp(self):
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
