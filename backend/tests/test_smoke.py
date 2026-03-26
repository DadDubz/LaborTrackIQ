import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TEMP_DIR.name) / 'test.db'}"
os.environ["SECRET_KEY"] = "labortrackiq-test-secret"

from fastapi.testclient import TestClient

from app.db.session import Base, SessionLocal, engine
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

    def test_employee_self_service_requires_headers(self):
        unauthorized = self.client.get("/api/employees/3/profile")
        self.assertEqual(unauthorized.status_code, 401, unauthorized.text)

        authorized = self.client.get("/api/employees/3/profile", headers=self.employee_headers())
        self.assertEqual(authorized.status_code, 200, authorized.text)
        self.assertEqual(authorized.json()["employee_number"], "1001")

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
                "start_date": date.today().isoformat(),
                "end_date": date.today().isoformat(),
            },
        )
        self.assertEqual(export.status_code, 200, export.text)
        summary = export.json()["export_summary"]
        self.assertEqual(summary["entries"], 1)


if __name__ == "__main__":
    unittest.main()
