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
