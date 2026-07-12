from __future__ import annotations

import secrets
import string

from django.conf import settings
from google_auth_oauthlib.flow import Flow


DEFAULT_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"


def generate_code_verifier(length: int = 64) -> str:
    """
    PKCE code_verifier:
    random string between 43 and 128 characters.
    """
    alphabet = string.ascii_letters + string.digits + "-._~"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _client_config():
    return {
        "web": {
            "client_id": settings.GOOGLE_STREETVIEW_CLIENT_ID,
            "client_secret": settings.GOOGLE_STREETVIEW_CLIENT_SECRET,
            "auth_uri": DEFAULT_AUTH_URI,
            "token_uri": DEFAULT_TOKEN_URI,
            "redirect_uris": [settings.GOOGLE_STREETVIEW_REDIRECT_URI],
        }
    }


def build_flow(
    *,
    state: str | None = None,
    code_verifier: str | None = None,
) -> Flow:
    flow = Flow.from_client_config(
        client_config=_client_config(),
        scopes=[settings.GOOGLE_STREETVIEW_SCOPE],
        state=state,
        code_verifier=code_verifier,
        autogenerate_code_verifier=False,
    )
    flow.redirect_uri = settings.GOOGLE_STREETVIEW_REDIRECT_URI
    return flow


def get_authorization_url(*, code_verifier: str):
    flow = build_flow(code_verifier=code_verifier)

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    return authorization_url, state


def fetch_credentials_from_callback(
    authorization_response: str,
    *,
    state: str,
    code_verifier: str,
):
    flow = build_flow(
        state=state,
        code_verifier=code_verifier,
    )
    flow.fetch_token(authorization_response=authorization_response)
    return flow.credentials


def credentials_to_account_defaults(credentials):
    scopes = credentials.scopes or [settings.GOOGLE_STREETVIEW_SCOPE]

    return {
        "access_token": credentials.token or "",
        "refresh_token": credentials.refresh_token or "",
        "token_uri": credentials.token_uri or DEFAULT_TOKEN_URI,
        "scopes": " ".join(scopes),
        "token_expiry": credentials.expiry,
    }