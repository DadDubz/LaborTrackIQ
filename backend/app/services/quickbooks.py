from __future__ import annotations

import secrets
from base64 import b64encode
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from app.core.config import settings


AUTHORIZATION_URL = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"


def require_quickbooks_credentials() -> None:
    if not settings.quickbooks_client_id or not settings.quickbooks_client_secret:
        raise HTTPException(
            status_code=503,
            detail=(
                "QuickBooks OAuth is not configured. Set QUICKBOOKS_CLIENT_ID and "
                "QUICKBOOKS_CLIENT_SECRET before using live QuickBooks auth."
            ),
        )


def build_authorization_url(state: str) -> str:
    require_quickbooks_credentials()
    query = urlencode(
        {
            "client_id": settings.quickbooks_client_id,
            "response_type": "code",
            "scope": settings.quickbooks_scopes,
            "redirect_uri": settings.quickbooks_redirect_uri,
            "state": state,
        }
    )
    return f"{AUTHORIZATION_URL}?{query}"


def generate_state_token() -> str:
    return secrets.token_urlsafe(32)


def token_expiry(expires_in_seconds: int) -> str:
    return (datetime.utcnow() + timedelta(seconds=expires_in_seconds)).isoformat()


def exchange_code_for_tokens(code: str) -> dict:
    require_quickbooks_credentials()
    basic = b64encode(f"{settings.quickbooks_client_id}:{settings.quickbooks_client_secret}".encode("utf-8")).decode("utf-8")
    response = httpx.post(
        TOKEN_URL,
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.quickbooks_redirect_uri,
        },
        timeout=20.0,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"QuickBooks token exchange failed: {response.text}")
    return response.json()


def refresh_tokens(refresh_token: str) -> dict:
    require_quickbooks_credentials()
    basic = b64encode(f"{settings.quickbooks_client_id}:{settings.quickbooks_client_secret}".encode("utf-8")).decode("utf-8")
    response = httpx.post(
        TOKEN_URL,
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=20.0,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"QuickBooks token refresh failed: {response.text}")
    return response.json()
