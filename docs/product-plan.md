# LaborTrackIQ Product Plan

## Product Direction

LaborTrackIQ is a workforce operations platform for hospitality, retail, and service businesses that need:

- A shared tablet kiosk for clock in/out
- Schedule visibility for employees
- Role-based admin and manager access
- Labor reporting for owners and finance users
- Accounting integrations, starting with QuickBooks
- Shift-start communication from management to staff

## Personas

- Owner/Admin: creates the business account, manages users, integrations, and report access
- Manager: creates schedules, sends notes, reviews attendance
- Employee: clocks in/out, views schedule, sees notes
- Finance/Operations Viewer: receives and reviews reports without editing employees

## Functional Requirements

### Shared Tablet Time Clock

- Employees can clock in and out with employee ID + PIN
- Tablet view is optimized for touch targets and quick actions
- System blocks duplicate active clock-ins
- System records labor totals and clock source device

### Scheduling

- Managers can assign schedule shifts
- Employees can view upcoming shifts
- Clock terminal can show "next scheduled shift"

### Messaging

- Managers/admins can post notes to one employee or all employees
- Notes can require acknowledgement later in the roadmap
- Active notes display at clock-in

### Reporting

- Owners can add multiple report recipients under the organization
- Reports should support daily labor summary, missed punches, and overtime risk

### Multi-Tenant Account Structure

- One organization contains many users
- One admin owns the organization
- Admin can create managers, employees, and report viewers

### Accounting Integrations

- QuickBooks Online should be the first integration
- Integration layer should be provider-based so Xero, Gusto, ADP, or Restaurant365 can be added later

## Technical Recommendation

### Backend

- FastAPI
- SQLAlchemy ORM
- PostgreSQL in production
- Alembic for migrations
- Background jobs for report generation and integration syncs

### Frontend

- React + Vite
- Responsive tablet-first layout
- Separate kiosk and admin experiences

### Authentication

- Admin/manager login with email + password
- Employee kiosk access with employee number + PIN
- Organization-scoped authorization

## Integration Strategy

Use a generic connector contract:

- `provider`: quickbooks, xero, gusto, adp, etc.
- `status`: disconnected, pending, connected, error
- `credentials_ref`: encrypted token reference
- `settings`: export mappings, payroll codes, location mappings

QuickBooks initial sync opportunities:

- Export employee hours by date range
- Sync classes/departments
- Sync labor cost summary for bookkeeping workflows

## Reporting Roadmap

- Daily labor summary
- Tardy/absence report
- Missed punches report
- Overtime risk report
- Labor vs schedule variance

## Future Enhancements

- Geofenced mobile clock-in
- Break tracking
- Time-off requests
- Payroll approval workflows
- Push notifications and SMS reminders
