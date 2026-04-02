# Deployment Runbook

## 1. Environment baseline

- Start from `ops/env/backend.production.env.example`
- Set `APP_ENVIRONMENT=production`
- Set a strong `SECRET_KEY`
- Set `ALLOW_DEMO_BOOTSTRAP=false`
- Set `MAX_REQUEST_BYTES` (default `1048576`) to cap request size
- Set auth/clock rate limits (`AUTH_RATE_LIMIT`, `AUTH_ACCOUNT_RATE_LIMIT`, `CLOCK_RATE_LIMIT`, `CLOCK_EMPLOYEE_RATE_LIMIT`) for your traffic profile
- Set `TRUST_PROXY_HEADERS=true` only when deployed behind a trusted reverse proxy
- Set `QUICKBOOKS_OAUTH_STATE_TTL_SECONDS` (default `900`) to limit OAuth callback replay window
- Set production `CORS_ORIGINS`
- Set `DATABASE_URL` to PostgreSQL

## 2. Database migration

Run migrations before app traffic:

```bash
cd backend
alembic -c alembic.ini upgrade head
```

For legacy environments with existing schema:

```bash
cd backend
alembic -c alembic.ini stamp head
```

Rollback one revision if needed:

```bash
cd backend
alembic -c alembic.ini downgrade -1
```

Rollback to base (disaster recovery only):

```bash
cd backend
alembic -c alembic.ini downgrade base
```

## 3. Preflight validation

Run preflight checks before applying traffic:

```bash
PYTHONPATH=backend ../.venv/bin/python backend/scripts/preflight.py --strict
```

Or run the full release gate from repo root:

```bash
make release-gate
```

For local/dev pipelines, use:

```bash
make release-gate-dev
```

## 4. Health checks

- App health: `GET /health`
- DB health: `GET /health/db`
- Readiness: `GET /health/ready`

Both must return `200` before routing traffic.

## 5. Containerized local/prod-like boot

From repo root:

```bash
docker compose up --build
```

Backend will be available at `http://127.0.0.1:8000`.

## 6. Post-deploy checks

- Admin login works
- Employee clock in/out works
- Schedule publish/unpublish works
- Smoke suite passes in CI
