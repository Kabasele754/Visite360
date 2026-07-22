from __future__ import annotations

import re
from urllib.parse import urlparse


def validate_response(*, answer: str, citations: list[dict], require_citations: bool = True) -> dict:
    allowed_ids = {item["id"] for item in citations}
    used_ids = set(re.findall(r"\[(K\d+)\]", answer))
    invalid_ids = sorted(used_ids - allowed_ids)
    uncited = require_citations and bool(citations) and not used_ids
    allowed_hosts = {urlparse(item.get("url", "")).hostname for item in citations if item.get("url")}
    links = re.findall(r"https?://[^\s)\]]+", answer)
    unverified_links = [url for url in links if urlparse(url).hostname not in allowed_hosts]
    passed = not invalid_ids and not uncited and not unverified_links
    return {
        "passed": passed,
        "used_citations": sorted(used_ids),
        "invalid_citations": invalid_ids,
        "missing_citations": uncited,
        "unverified_links": unverified_links,
    }
