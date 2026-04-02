import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import HTTPException


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ["QUICKBOOKS_CLIENT_ID"] = "test-client-id"
os.environ["QUICKBOOKS_CLIENT_SECRET"] = "test-client-secret"

from app.services import quickbooks


class QuickBooksServiceTests(unittest.TestCase):
    def setUp(self):
        self.original_client_id = quickbooks.settings.quickbooks_client_id
        self.original_client_secret = quickbooks.settings.quickbooks_client_secret
        quickbooks.settings.quickbooks_client_id = "test-client-id"
        quickbooks.settings.quickbooks_client_secret = "test-client-secret"

    def tearDown(self):
        quickbooks.settings.quickbooks_client_id = self.original_client_id
        quickbooks.settings.quickbooks_client_secret = self.original_client_secret

    def test_exchange_code_network_error_returns_502(self):
        with patch("app.services.quickbooks.httpx.post", side_effect=httpx.RequestError("network down")):
            with self.assertRaises(HTTPException) as context:
                quickbooks.exchange_code_for_tokens("test-code")

        self.assertEqual(context.exception.status_code, 502)
        self.assertIn("network error", str(context.exception.detail).lower())

    def test_exchange_code_non_json_error_does_not_echo_raw_body(self):
        response = httpx.Response(status_code=400, text="sensitive upstream body details")
        with patch("app.services.quickbooks.httpx.post", return_value=response):
            with self.assertRaises(HTTPException) as context:
                quickbooks.exchange_code_for_tokens("test-code")

        self.assertEqual(context.exception.status_code, 502)
        self.assertIn("HTTP 400", str(context.exception.detail))
        self.assertNotIn("sensitive upstream body details", str(context.exception.detail))

    def test_refresh_tokens_uses_fault_message_when_available(self):
        response = httpx.Response(
            status_code=401,
            json={"Fault": {"Error": [{"Message": "Invalid refresh token"}]}},
        )
        with patch("app.services.quickbooks.httpx.post", return_value=response):
            with self.assertRaises(HTTPException) as context:
                quickbooks.refresh_tokens("expired-refresh-token")

        self.assertEqual(context.exception.status_code, 502)
        self.assertIn("Invalid refresh token", str(context.exception.detail))


if __name__ == "__main__":
    unittest.main()
