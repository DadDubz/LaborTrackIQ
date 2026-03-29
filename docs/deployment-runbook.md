# Deployment Runbook

## 1. Environment baseline

- Set `APP_ENVIRONMENT=production`
- Set a strong `SECRET_KEY`
- Set `ALLOW_DEMO_BOOTSTRAP=false`
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

## 3. Health checks

- App health: `GET /health`
- DB health: `GET /health/db`

Both must return `200` before routing traffic.

## 4. Containerized local/prod-like boot

From repo root:

```bash
docker compose up --build
```

Backend will be available at `http://127.0.0.1:8000`.

## 5. Post-deploy checks

- Admin login works
- Employee clock in/out works
- Schedule publish/unpublish works
- Smoke suite passes in CI
