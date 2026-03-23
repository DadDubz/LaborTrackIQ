# QuickBooks Setup

## Local Environment

Create a `.env` file in the repository root using `.env.example` as the template.

Required values for live OAuth:

- `QUICKBOOKS_CLIENT_ID`
- `QUICKBOOKS_CLIENT_SECRET`
- `QUICKBOOKS_REDIRECT_URI`

Recommended local redirect URI:

- `http://127.0.0.1:8000/api/integrations/quickbooks/callback`

## Local Flow

1. Create an Intuit developer app
2. Set the redirect URI in the Intuit app settings
3. Add the client ID and client secret to `.env`
4. Restart the backend
5. Open the Integrations tab in LaborTrackIQ
6. Generate the OAuth URL and complete the QuickBooks consent screen

## Current Behavior

- If QuickBooks credentials are missing, the OAuth URL endpoint returns `503` with a setup message
- The integration tab shows whether credentials are configured
- The callback route is ready to exchange auth codes for tokens

## Production Note

The current token sealing approach is suitable for local development and MVP staging. For production, replace it with a real secret manager or KMS-backed encryption flow.
