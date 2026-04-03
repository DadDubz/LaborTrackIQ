from __future__ import annotations

import argparse
import sys

from app.core.config import settings


def _is_default_secret() -> bool:
    return settings.secret_key == "labortrackiq-dev-secret"


def _is_sqlite_database() -> bool:
    return settings.database_url.startswith("sqlite")


def run_preflight(strict: bool = False) -> int:
    failures: list[str] = []
    warnings: list[str] = []
    environment = settings.app_environment.lower()

    if not settings.cors_origins:
        failures.append("CORS_ORIGINS must include at least one allowed origin.")

    if _is_default_secret():
        message = "SECRET_KEY is still set to the development default."
        if strict or environment in {"production", "staging"}:
            failures.append(message)
        else:
            warnings.append(message)

    if environment in {"production", "staging"}:
        if settings.allow_demo_bootstrap:
            failures.append("ALLOW_DEMO_BOOTSTRAP must be false in production/staging.")
        if _is_sqlite_database():
            failures.append("DATABASE_URL must point to PostgreSQL in production/staging (SQLite is not supported).")
    elif _is_sqlite_database():
        warnings.append("Using SQLite database URL for this environment.")

    numeric_settings = [
        ("MAX_REQUEST_BYTES", settings.max_request_bytes),
        ("AUTH_RATE_LIMIT", settings.auth_rate_limit),
        ("AUTH_RATE_WINDOW_SECONDS", settings.auth_rate_window_seconds),
        ("AUTH_ACCOUNT_RATE_LIMIT", settings.auth_account_rate_limit),
        ("AUTH_ACCOUNT_RATE_WINDOW_SECONDS", settings.auth_account_rate_window_seconds),
        ("CLOCK_RATE_LIMIT", settings.clock_rate_limit),
        ("CLOCK_RATE_WINDOW_SECONDS", settings.clock_rate_window_seconds),
        ("CLOCK_EMPLOYEE_RATE_LIMIT", settings.clock_employee_rate_limit),
        ("CLOCK_EMPLOYEE_RATE_WINDOW_SECONDS", settings.clock_employee_rate_window_seconds),
        ("QUICKBOOKS_OAUTH_STATE_TTL_SECONDS", settings.quickbooks_oauth_state_ttl_seconds),
    ]
    for key, value in numeric_settings:
        if value <= 0:
            failures.append(f"{key} must be greater than 0.")

    if failures:
        print("Preflight check failed:")
        for item in failures:
            print(f" - {item}")
        if warnings:
            print("Warnings:")
            for item in warnings:
                print(f" - {item}")
        return 1

    print("Preflight check passed.")
    if warnings:
        print("Warnings:")
        for item in warnings:
            print(f" - {item}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LaborTrackIQ deployment preflight checks.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat development defaults as failures even outside production/staging.",
    )
    args = parser.parse_args()
    return run_preflight(strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
