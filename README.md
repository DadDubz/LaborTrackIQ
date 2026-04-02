# LaborTrackIQ

LaborTrackIQ is a tablet-friendly workforce app foundation for:

- Employee clock in and clock out
- Viewing schedules on iPads and tablets
- Manager and admin notes shown at clock-in
- Multi-user reporting access under one business admin
- QuickBooks and future accounting integration hooks

This repository starts with an MVP-ready architecture:

- `backend/`: FastAPI service with SQLAlchemy models and REST endpoints
- `frontend/`: React + Vite tablet-first UI scaffold
- `docs/`: product and integration planning

## MVP Goals

The first release is designed to support a single business location or a small group of locations with:

- One organization owner or admin
- Admin-created manager and employee accounts
- PIN-based employee clock terminal flow for shared tablets
- Schedule viewing by employee
- Manager notes surfaced when employees clock in
- Reporting-ready labor data storage

## Core Data Model

- `organizations`: each customer account/business
- `users`: admin, manager, employee accounts
- `employee_profiles`: employee IDs, PINs, payroll metadata
- `schedule_shifts`: scheduled work windows
- `time_entries`: clock in/out records
- `manager_notes`: notes/messages for employees
- `report_subscriptions`: who receives reports
- `integration_connections`: QuickBooks and other accounting apps

Employee PINs are stored as hashed values (`pin_hash`) with legacy plaintext records automatically upgraded on successful login.

## Local Structure

```text
backend/
  app/
frontend/
docs/
```

## Local Setup

1. Copy `.env.example` to `.env`
2. Set `APP_ENVIRONMENT`, `SECRET_KEY`, and `CORS_ORIGINS` for your environment, and set `ALLOW_DEMO_BOOTSTRAP=false` outside local development
3. Add your QuickBooks OAuth credentials when you are ready to test live QuickBooks auth
4. Install backend requirements with `.venv/bin/pip install -r backend/requirements.txt`
5. Install frontend packages with `npm install` in `frontend/`
6. Start the API with `../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000` from `backend/`
7. Start the frontend with `npm run dev -- --host 127.0.0.1 --port 5173` from `frontend/`

QuickBooks setup details live in `docs/quickbooks-setup.md`.
Deployment guidance lives in `docs/deployment-runbook.md`.

## Database Migrations

Alembic is configured under `backend/alembic/`.

```bash
cd backend
../.venv/bin/alembic -c alembic.ini upgrade head
```

For existing environments that already have tables, run:

```bash
cd backend
../.venv/bin/alembic -c alembic.ini stamp head
```

Rollback one migration:

```bash
make migrate-down-one
```

Rollback to base:

```bash
make migrate-down-base
```

## Preflight Checks

Run deployment preflight checks with:

```bash
make preflight
```

For stricter validation (including rejecting development defaults in any environment):

```bash
make preflight-strict
```

Run the full release gate:

```bash
make release-gate
```

For local/dev-safe release checks:

```bash
make release-gate-dev
```

## Smoke Tests

Run the backend smoke suite with:

```bash
.venv/bin/python -m unittest discover -s backend/tests -p "test_*.py"
```

The smoke tests cover launch-critical flows like employee self-service auth, duplicate identity protection, report recipient handling, and payroll-only labor export behavior.

## Health Endpoints

- `GET /health`
- `GET /health/db`
- `GET /health/ready`

## Docker Compose

You can run backend + PostgreSQL with:

```bash
docker compose up --build
```

## Suggested Next Steps

1. Add authentication and permissions with JWT or session auth
2. Add persistent PostgreSQL configuration for production
3. Add QuickBooks OAuth sync flows
4. Add reporting jobs and email delivery
5. Add location/device management for shared kiosks
