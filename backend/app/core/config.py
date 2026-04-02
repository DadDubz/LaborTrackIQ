from pathlib import Path
import os
from typing import List

from dotenv import load_dotenv
from pydantic import BaseModel


ROOT_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]

load_dotenv(ROOT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")


def _parse_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(value: str, default: List[str]) -> List[str]:
    if not value:
        return default
    parts = [item.strip() for item in value.split(",")]
    return [item for item in parts if item]


class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "LaborTrackIQ API")
    app_environment: str = os.getenv("APP_ENVIRONMENT", "development")
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{(BACKEND_DIR / 'labortrackiq.db').resolve()}")
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    secret_key: str = os.getenv("SECRET_KEY", "labortrackiq-dev-secret")
    quickbooks_client_id: str = os.getenv("QUICKBOOKS_CLIENT_ID", "")
    quickbooks_client_secret: str = os.getenv("QUICKBOOKS_CLIENT_SECRET", "")
    quickbooks_redirect_uri: str = os.getenv(
        "QUICKBOOKS_REDIRECT_URI",
        "http://127.0.0.1:8000/api/integrations/quickbooks/callback",
    )
    quickbooks_environment: str = os.getenv("QUICKBOOKS_ENVIRONMENT", "sandbox")
    quickbooks_scopes: str = os.getenv("QUICKBOOKS_SCOPES", "com.intuit.quickbooks.accounting")
    allow_demo_bootstrap: bool = _parse_bool(os.getenv("ALLOW_DEMO_BOOTSTRAP"), True)
    max_request_bytes: int = int(os.getenv("MAX_REQUEST_BYTES", "1048576"))
    auth_rate_limit: int = int(os.getenv("AUTH_RATE_LIMIT", "20"))
    auth_rate_window_seconds: int = int(os.getenv("AUTH_RATE_WINDOW_SECONDS", "60"))
    clock_rate_limit: int = int(os.getenv("CLOCK_RATE_LIMIT", "60"))
    clock_rate_window_seconds: int = int(os.getenv("CLOCK_RATE_WINDOW_SECONDS", "60"))
    trust_proxy_headers: bool = _parse_bool(os.getenv("TRUST_PROXY_HEADERS"), False)
    cors_origins: List[str] = _parse_csv(
        os.getenv("CORS_ORIGINS"),
        ["http://127.0.0.1:5173", "http://localhost:5173"],
    )


settings = Settings()
