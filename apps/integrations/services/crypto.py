from __future__ import annotations

import base64
import hashlib
import json
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _key() -> bytes:
    configured = settings.INTEGRATION_ENCRYPTION_KEY.strip()
    if configured:
        raw = configured.encode("utf-8")
        try:
            decoded = base64.urlsafe_b64decode(raw)
            if len(decoded) == 32:
                return raw
        except Exception:
            pass
        return base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
    return base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest())


def encrypt_json(value: dict) -> str:
    payload = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return Fernet(_key()).encrypt(payload).decode("ascii")


def decrypt_json(value: str) -> dict:
    if not value:
        return {}
    try:
        payload = Fernet(_key()).decrypt(value.encode("ascii"))
        result = json.loads(payload.decode("utf-8"))
        return result if isinstance(result, dict) else {}
    except (InvalidToken, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Unable to decrypt integration credentials.") from exc
