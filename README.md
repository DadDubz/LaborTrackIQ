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

## Local Structure

```text
backend/
  app/
frontend/
docs/
```

## Suggested Next Steps

1. Add authentication and permissions with JWT or session auth
2. Add persistent PostgreSQL configuration for production
3. Add QuickBooks OAuth sync flows
4. Add reporting jobs and email delivery
5. Add location/device management for shared kiosks
