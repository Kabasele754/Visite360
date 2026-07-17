"""Twinscopes Growth AI configuration.

Secrets are read from Docker secret files first (NAME_FILE), then from the
regular environment variable NAME. DataSourceConnection stores only the
credential reference, never the actual secret.
"""

import os
from pathlib import Path

from decouple import config


def _read_growth_secret(name: str, default: str = "") -> str:
    file_path = os.getenv(f"{name}_FILE", "").strip()
    if file_path:
        try:
            return Path(file_path).read_text(encoding="utf-8").strip()
        except OSError:
            pass
    return os.getenv(name, default).strip()


GROWTH_AI_ENABLED = config("GROWTH_AI_ENABLED", default=True, cast=bool)
GROWTH_AI_DEFAULT_LOOKBACK_DAYS = config(
    "GROWTH_AI_DEFAULT_LOOKBACK_DAYS",
    default=7,
    cast=int,
)
GROWTH_AI_EVENT_RETENTION_DAYS = config(
    "GROWTH_AI_EVENT_RETENTION_DAYS",
    default=730,
    cast=int,
)
GROWTH_AI_SYNC_RUN_RETENTION_DAYS = config(
    "GROWTH_AI_SYNC_RUN_RETENTION_DAYS",
    default=180,
    cast=int,
)

GOOGLE_GROWTH_CLIENT_ID = _read_growth_secret(
    "GOOGLE_GROWTH_CLIENT_ID",
    config("GOOGLE_GROWTH_CLIENT_ID", default=""),
)
GOOGLE_GROWTH_CLIENT_SECRET = _read_growth_secret(
    "GOOGLE_GROWTH_CLIENT_SECRET",
    config("GOOGLE_GROWTH_CLIENT_SECRET", default=""),
)
GOOGLE_GROWTH_REFRESH_TOKEN = _read_growth_secret(
    "GOOGLE_GROWTH_REFRESH_TOKEN",
    config("GOOGLE_GROWTH_REFRESH_TOKEN", default=""),
)
GOOGLE_GROWTH_ACCESS_TOKEN = _read_growth_secret(
    "GOOGLE_GROWTH_ACCESS_TOKEN",
    config("GOOGLE_GROWTH_ACCESS_TOKEN", default=""),
)
BING_WEBMASTER_API_KEY = _read_growth_secret(
    "BING_WEBMASTER_API_KEY",
    config("BING_WEBMASTER_API_KEY", default=""),
)

GOOGLE_GROWTH_SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/business.manage",
]

GROWTH_AI_CREDENTIALS = {
    "google_main": {
        "client_id": GOOGLE_GROWTH_CLIENT_ID,
        "client_secret": GOOGLE_GROWTH_CLIENT_SECRET,
        "refresh_token": GOOGLE_GROWTH_REFRESH_TOKEN,
        "access_token": GOOGLE_GROWTH_ACCESS_TOKEN,
        "scopes": GOOGLE_GROWTH_SCOPES,
    },
    "bing_main": {
        "api_key": BING_WEBMASTER_API_KEY,
    },
}
