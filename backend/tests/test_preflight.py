import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from scripts.preflight import run_preflight


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self._original = {
            "app_environment": settings.app_environment,
            "secret_key": settings.secret_key,
            "allow_demo_bootstrap": settings.allow_demo_bootstrap,
            "database_url": settings.database_url,
            "cors_origins": list(settings.cors_origins),
            "max_request_bytes": settings.max_request_bytes,
            "auth_rate_limit": settings.auth_rate_limit,
            "auth_rate_window_seconds": settings.auth_rate_window_seconds,
            "auth_account_rate_limit": settings.auth_account_rate_limit,
            "auth_account_rate_window_seconds": settings.auth_account_rate_window_seconds,
            "clock_rate_limit": settings.clock_rate_limit,
            "clock_rate_window_seconds": settings.clock_rate_window_seconds,
            "clock_employee_rate_limit": settings.clock_employee_rate_limit,
            "clock_employee_rate_window_seconds": settings.clock_employee_rate_window_seconds,
            "quickbooks_oauth_state_ttl_seconds": settings.quickbooks_oauth_state_ttl_seconds,
        }
        settings.app_environment = "development"
        settings.secret_key = "labortrackiq-test-secret"
        settings.allow_demo_bootstrap = True
        settings.database_url = "sqlite:///tmp/test.db"
        settings.cors_origins = ["http://127.0.0.1:5173"]
        settings.max_request_bytes = 1
        settings.auth_rate_limit = 1
        settings.auth_rate_window_seconds = 1
        settings.auth_account_rate_limit = 1
        settings.auth_account_rate_window_seconds = 1
        settings.clock_rate_limit = 1
        settings.clock_rate_window_seconds = 1
        settings.clock_employee_rate_limit = 1
        settings.clock_employee_rate_window_seconds = 1
        settings.quickbooks_oauth_state_ttl_seconds = 1

    def tearDown(self):
        for key, value in self._original.items():
            setattr(settings, key, value)

    def test_preflight_passes_with_valid_numeric_settings(self):
        self.assertEqual(run_preflight(strict=False), 0)

    def test_preflight_fails_when_numeric_setting_is_non_positive(self):
        settings.auth_account_rate_limit = 0
        self.assertEqual(run_preflight(strict=False), 1)

    def test_preflight_fails_in_production_with_invalid_numeric_setting(self):
        settings.app_environment = "production"
        settings.allow_demo_bootstrap = False
        settings.database_url = "postgresql+psycopg://user:pass@db:5432/labortrackiq"
        settings.clock_employee_rate_window_seconds = -1
        self.assertEqual(run_preflight(strict=False), 1)


if __name__ == "__main__":
    unittest.main()
