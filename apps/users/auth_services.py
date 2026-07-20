import hashlib
import json
import logging
import secrets
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def unique_username(email: str) -> str:
    base = (email.split("@", 1)[0] or "user").lower()
    base = "".join(ch for ch in base if ch.isalnum() or ch in "._-")[:120] or "user"
    candidate = base
    counter = 1
    while User.objects.filter(username=candidate).exists():
        counter += 1
        candidate = f"{base[:110]}-{counter}"
    return candidate


def split_name(full_name: str):
    parts = [part for part in (full_name or "").strip().split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def create_email_user(*, full_name: str, email: str, phone: str, password: str):
    first_name, last_name = split_name(full_name)
    return User.objects.create_user(
        username=unique_username(email),
        email=email.lower(),
        password=password,
        first_name=first_name,
        last_name=last_name,
        phone=phone.strip(),
        is_customer=True,
    )


def google_settings():
    client_id = getattr(settings, "GOOGLE_AUTH_CLIENT_ID", "") or getattr(settings, "GOOGLE_GROWTH_CLIENT_ID", "")
    client_secret = getattr(settings, "GOOGLE_AUTH_CLIENT_SECRET", "") or getattr(settings, "GOOGLE_GROWTH_CLIENT_SECRET", "")
    redirect_uri = getattr(settings, "GOOGLE_AUTH_REDIRECT_URI", "")
    return client_id, client_secret, redirect_uri


def build_google_authorization_url(request, next_url: str) -> str:
    client_id, _, redirect_uri = google_settings()
    if not client_id or not redirect_uri:
        raise RuntimeError("Google authentication is not configured.")
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    request.session["google_auth_state"] = state
    request.session["google_auth_nonce"] = nonce
    request.session["google_auth_next"] = next_url
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "prompt": "select_account",
        "access_type": "online",
        "include_granted_scopes": "true",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def _post_form(url: str, data: dict) -> dict:
    body = urlencode(data).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str, access_token: str) -> dict:
    request = Request(url, headers={"Authorization": f"Bearer {access_token}"})
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def exchange_google_code(code: str) -> dict:
    client_id, client_secret, redirect_uri = google_settings()
    if not client_id or not client_secret or not redirect_uri:
        raise RuntimeError("Google authentication is not configured.")
    token = _post_form(
        GOOGLE_TOKEN_URL,
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    access_token = token.get("access_token")
    if not access_token:
        raise RuntimeError("Google did not return an access token.")
    profile = _get_json(GOOGLE_USERINFO_URL, access_token)
    if not profile.get("email") or not profile.get("email_verified"):
        raise RuntimeError("A verified Google email is required.")
    return profile


def get_or_create_google_user(profile: dict):
    email = profile["email"].strip().lower()
    defaults = {
        "username": unique_username(email),
        "first_name": (profile.get("given_name") or "")[:150],
        "last_name": (profile.get("family_name") or "")[:150],
        "is_customer": True,
        "email_verified_at": timezone.now(),
    }
    user, created = User.objects.get_or_create(email__iexact=email, defaults={"email": email, **defaults})
    changed = []
    if not created:
        if not user.email_verified_at:
            user.email_verified_at = timezone.now(); changed.append("email_verified_at")
        if not user.first_name and defaults["first_name"]:
            user.first_name = defaults["first_name"]; changed.append("first_name")
        if not user.last_name and defaults["last_name"]:
            user.last_name = defaults["last_name"]; changed.append("last_name")
        if changed:
            user.save(update_fields=changed)
    return user, created
