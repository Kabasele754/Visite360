from __future__ import annotations

from datetime import timezone as dt_timezone

from django.conf import settings
from django.utils import timezone
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


class GoogleStreetViewAuthError(Exception):
    pass


def _to_google_naive_utc(value):
    """
    google-auth compares expiry with a naive UTC datetime internally.
    Django with USE_TZ=True stores aware datetimes, so we must convert before
    creating Credentials, otherwise Python raises:
    can't compare offset-naive and offset-aware datetimes.
    """
    if not value:
        return None
    if timezone.is_aware(value):
        return value.astimezone(dt_timezone.utc).replace(tzinfo=None)
    return value


def _to_django_aware_utc(value):
    """
    google-auth returns expiry as a naive UTC datetime.
    Convert it back to an aware UTC datetime before saving into Django.
    """
    if not value:
        return None
    if timezone.is_naive(value):
        return value.replace(tzinfo=dt_timezone.utc)
    return value.astimezone(dt_timezone.utc)


def build_credentials(account) -> Credentials:
    """
    Build Google OAuth credentials from the DB account.
    The expiry passed to google-auth must be naive UTC.
    """
    scopes = account.scopes.split() if account.scopes else [settings.GOOGLE_STREETVIEW_SCOPE]

    return Credentials(
        token=account.access_token or None,
        refresh_token=account.refresh_token or None,
        token_uri=account.token_uri or "https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_STREETVIEW_CLIENT_ID,
        client_secret=settings.GOOGLE_STREETVIEW_CLIENT_SECRET,
        scopes=scopes,
        expiry=_to_google_naive_utc(account.token_expiry),
    )


def get_valid_access_token(account) -> str:
    """
    Return a fresh access token for Street View Publish API.

    If the stored token is expired, refresh it using the refresh token and save
    the new access_token + token_expiry in the database.
    """
    if not account:
        raise GoogleStreetViewAuthError("Compte Google Street View non connecté.")

    credentials = build_credentials(account)

    should_refresh = (
        not credentials.token
        or not account.token_expiry
        or credentials.expired
        or not credentials.valid
    )

    if should_refresh:
        if not credentials.refresh_token:
            raise GoogleStreetViewAuthError(
                "Session Google expirée. Reconnecte ton compte Google Street View."
            )

        try:
            credentials.refresh(Request())
        except RefreshError as exc:
            raise GoogleStreetViewAuthError(
                "Impossible de rafraîchir la session Google. "
                f"Reconnecte le compte Google. Détail: {exc}"
            ) from exc

        update_fields = ["access_token", "token_expiry", "updated_at"]
        account.access_token = credentials.token or ""
        account.token_expiry = _to_django_aware_utc(credentials.expiry)

        # Google usually returns the refresh token only during the first consent,
        # but keep this safe if it is ever rotated.
        if credentials.refresh_token and credentials.refresh_token != account.refresh_token:
            account.refresh_token = credentials.refresh_token
            update_fields.append("refresh_token")

        account.save(update_fields=update_fields)

    token = credentials.token or account.access_token

    if not token:
        raise GoogleStreetViewAuthError(
            "Token Google absent. Reconnecte ton compte Google Street View."
        )

    return token
