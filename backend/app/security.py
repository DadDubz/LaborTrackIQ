import hashlib
import hmac
import json
import os
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException

from app.core.config import settings


def _b64encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}")


def _derive_key(salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", settings.secret_key.encode("utf-8"), salt, 200_000, dklen=32)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, stored_hash: Optional[str]) -> bool:
    if not stored_hash or ":" not in stored_hash:
        return False

    salt_hex, digest_hex = stored_hash.split(":", 1)
    salt = bytes.fromhex(salt_hex)
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return hmac.compare_digest(candidate.hex(), digest_hex)


def create_access_token(user_id: int, organization_id: int, role: str, expires_in_hours: int = 12) -> str:
    payload = {
        "user_id": user_id,
        "organization_id": organization_id,
        "role": role,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)).timestamp()),
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(settings.secret_key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return f"{body}.{_b64encode(signature)}"


def decode_access_token(token: str) -> dict:
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token format.") from exc

    expected_signature = hmac.new(settings.secret_key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64encode(expected_signature), signature):
        raise HTTPException(status_code=401, detail="Invalid token signature.")

    payload = json.loads(_b64decode(body).decode("utf-8"))
    if payload.get("exp", 0) < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status_code=401, detail="Token expired.")
    return payload


def seal_secret(value: dict) -> str:
    payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
    salt = os.urandom(16)
    key = _derive_key(salt)
    ciphertext = bytes(byte ^ key[index % len(key)] for index, byte in enumerate(payload))
    body = _b64encode(salt + ciphertext)
    signature = hmac.new(settings.secret_key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return f"{body}.{_b64encode(signature)}"


def unseal_secret(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Stored credential blob is invalid.") from exc

    expected = hmac.new(settings.secret_key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64encode(expected), signature):
        raise HTTPException(status_code=400, detail="Stored credential signature is invalid.")

    raw = _b64decode(body)
    salt, ciphertext = raw[:16], raw[16:]
    key = _derive_key(salt)
    plaintext = bytes(byte ^ key[index % len(key)] for index, byte in enumerate(ciphertext))
    return json.loads(plaintext.decode("utf-8"))
