# Launch Checklist

This checklist is the working punch list for taking LaborTrackIQ from "looks good" to "safe to market and onboard real restaurants."

## 1. Launch Blockers

These items should be completed before sending real restaurants to the site.

- [ ] Set the production SMTP variables so access requests notify `info@labortrackiq.com`
  - Required settings:
    - `ACCESS_REQUEST_NOTIFICATION_EMAIL=info@labortrackiq.com`
    - `SMTP_HOST`
    - `SMTP_PORT`
    - `SMTP_USERNAME`
    - `SMTP_PASSWORD`
    - `SMTP_FROM_EMAIL`
  - Recommended defaults:
    - `SMTP_FROM_NAME=LaborTrackIQ`
    - `SMTP_USE_TLS=true`
    - `SMTP_USE_SSL=false`
- [ ] Apply the latest backend database migrations in production
  - Run `alembic -c alembic.ini upgrade head` from `backend/`
- [ ] Confirm production environment values are correct
  - `APP_ENVIRONMENT=production`
  - `ALLOW_DEMO_BOOTSTRAP=false`
  - Strong `SECRET_KEY`
  - Real production `DATABASE_URL`
  - Correct `CORS_ORIGINS`
  - `TRUST_PROXY_HEADERS=true` only when appropriate for hosting
- [ ] Verify the live request-access flow end to end
  - Submit a real request from the public site
  - Confirm the lead is stored in the database
  - Confirm the notification email reaches `info@labortrackiq.com`
- [ ] Verify the live auth and workforce flow end to end
  - Restaurant login works
  - Employee clock-in works
  - Manager/admin area loads correctly
  - Scheduling and notes screens save without errors
- [ ] Run the backend smoke suite in the real backend environment
  - `python -m unittest discover -s backend/tests -p "test_*.py"`
- [ ] Confirm readiness and health endpoints return success in production
  - `GET /health`
  - `GET /health/db`
  - `GET /health/ready`

## 2. First-Customer Readiness

These are the next items to complete before onboarding multiple restaurants.

- [ ] Decide the exact QuickBooks message for the marketing site
  - Use either "available now" or "coming soon"
  - Keep it consistent across the homepage, About page, and sales conversations
- [ ] Add a support and trust footer to the public site
  - `info@labortrackiq.com`
  - Privacy policy
  - Terms of service
- [ ] Add a basic onboarding process for new restaurants
  - Who receives the request
  - How you approve/setup the restaurant
  - What gets sent back to the customer after approval
- [ ] Add alerting or error monitoring
  - Backend error tracking
  - Frontend/Vercel deployment visibility
  - Notification if access-request email sending fails
- [ ] Create a real first-customer test script
  - Submit access request
  - Create organization/admin
  - Add manager
  - Add employee
  - Clock in/out
  - Publish schedule
  - Review labor reporting output
- [ ] Review permissions and data visibility
  - Managers should only see what they should manage
  - Employees should only see their own self-service data

## 3. Security and Hardening

These are the most important technical upgrades after the launch blockers.

- [ ] Replace `localStorage` auth storage with a more secure session/cookie approach
- [ ] Add password reset or admin-assisted credential recovery
- [ ] Add account lockout or escalation rules if repeated auth failures continue
- [ ] Review audit logging for admin and manager actions
- [ ] Confirm secrets are not stored in repo files or weak host settings
- [ ] Confirm backup/recovery process for the production database

## 4. Product Polish

These items improve credibility and make the app feel more complete during demos and onboarding.

- [ ] Add a dedicated confirmation/thank-you state after access request submission
- [ ] Add onboarding emails for approved restaurants
- [ ] Add invite-by-email flow for managers and employees
- [ ] Add a polished empty-state experience in the logged-in app
- [ ] Review every customer-facing screen for leftover internal wording
- [ ] Confirm favicon, logos, and marketing copy are consistent across all pages

## 5. Automation and Testing

These reduce risk every time the app changes.

- [ ] Add a committed Playwright smoke suite
  - Public homepage loads
  - About page loads
  - Restaurant login form renders
  - Request-access form submits successfully
- [ ] Add test scripts to `frontend/package.json` only when the suite is real and committed
- [ ] Add CI checks for backend smoke tests and frontend build

## 6. Launch Recommendation

LaborTrackIQ is close enough for controlled rollout once the launch blockers are done.

Best path:

1. Finish SMTP and live flow verification
2. Run one real production smoke pass
3. Add footer/legal basics
4. Start with a small number of pilot restaurants
5. Gather feedback before scaling outreach
