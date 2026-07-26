from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_ALLOWED_SCHEMES = {"http", "https"}
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]+")
_SPACE_RE = re.compile(r"\s+")


def _clean_text(value: Any, *, limit: int = 400) -> str:
    text = _CONTROL_RE.sub(" ", str(value or ""))
    text = _SPACE_RE.sub(" ", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip() + "…"
    return text


def _safe_public_url(value: Any) -> str:
    raw = _clean_text(value, limit=2000)
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES or not parsed.hostname:
        return ""
    if parsed.username or parsed.password:
        return ""
    hostname = parsed.hostname.encode("idna").decode("ascii").lower()
    port = parsed.port
    netloc = f"{hostname}:{port}" if port else hostname
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.lower(), netloc, path, parsed.query, ""))[:2000]


def serialize_public_sources(context: dict, *, limit: int = 8) -> list[dict]:
    output: list[dict] = []
    for item in (context.get("knowledge_sources") or [])[:limit]:
        if not isinstance(item, dict):
            continue
        citation = _clean_text(item.get("citation"), limit=16)
        if not re.fullmatch(r"K\d+", citation):
            continue
        output.append({
            "citation": citation,
            "title": _clean_text(item.get("title") or item.get("source") or "Official source", limit=180),
            "source": _clean_text(item.get("source") or "Official organization source", limit=120),
            "url": _safe_public_url(item.get("url")),
            "summary": _clean_text(item.get("content"), limit=320),
            "score": round(float(item.get("score") or 0), 4),
        })
    return output


def serialize_public_contact(contact: dict | None) -> dict:
    source = contact if isinstance(contact, dict) else {}
    social_links = {}
    for key, value in (source.get("social_links") or {}).items():
        url = _safe_public_url(value)
        if url:
            social_links[_clean_text(key, limit=30)] = url
    return {
        "organization_id": source.get("organization_id"),
        "organization_name": _clean_text(source.get("organization_name"), limit=160),
        "email": _clean_text(source.get("email"), limit=254),
        "phone": _clean_text(source.get("phone"), limit=80),
        "website": _safe_public_url(source.get("website")),
        "booking_url": _safe_public_url(source.get("booking_url")),
        "social_links": social_links,
    }
