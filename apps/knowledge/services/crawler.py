from __future__ import annotations

import hashlib
import ipaddress
import logging
import socket
from collections import deque
from dataclasses import dataclass
from typing import Any, MutableMapping
from urllib.parse import parse_qsl, urlencode, urldefrag, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from django.conf import settings

logger = logging.getLogger(__name__)


class UnsafeCrawlTarget(ValueError):
    pass


@dataclass(slots=True)
class CrawledPage:
    url: str
    title: str
    text: str
    html: str
    checksum: str


# High-value sections that commonly contain client-ready organization data.
# These are only attempted on the same official site and a failure never stops the crawl.
_PRIORITY_PATHS = (
    "",
    "about",
    "about-us",
    "who-we-are",
    "our-story",
    "company",
    "services",
    "our-services",
    "what-we-do",
    "departments",
    "specialties",
    "specialities",
    "treatments",
    "doctors",
    "medical-team",
    "team",
    "facilities",
    "rooms",
    "accommodation",
    "amenities",
    "properties",
    "listings",
    "contact",
    "contact-us",
    "book",
    "booking",
    "appointments",
)

_PRIORITY_TOKENS = {
    "about",
    "company",
    "contact",
    "service",
    "services",
    "department",
    "departments",
    "specialty",
    "specialties",
    "speciality",
    "specialities",
    "treatment",
    "treatments",
    "doctor",
    "doctors",
    "team",
    "facility",
    "facilities",
    "room",
    "rooms",
    "accommodation",
    "amenity",
    "amenities",
    "property",
    "properties",
    "listing",
    "listings",
    "booking",
    "appointment",
    "appointments",
}

_SKIP_EXTENSIONS = {
    ".7z", ".avi", ".bin", ".css", ".csv", ".doc", ".docx", ".eot", ".exe",
    ".gif", ".gz", ".ico", ".jpeg", ".jpg", ".js", ".json", ".m4a", ".mov",
    ".mp3", ".mp4", ".mpeg", ".ods", ".odt", ".pdf", ".png", ".ppt", ".pptx",
    ".rar", ".rss", ".svg", ".tar", ".tif", ".tiff", ".ttf", ".wav", ".webm",
    ".webp", ".woff", ".woff2", ".xls", ".xlsx", ".xml", ".zip",
}

_TRACKING_QUERY_KEYS = {
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "referrer", "source",
    "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term",
}


def _assert_public_hostname(hostname: str) -> None:
    if hostname in {"localhost", "localhost.localdomain"}:
        raise UnsafeCrawlTarget("Localhost is not allowed.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, None)}
    except socket.gaierror as exc:
        raise UnsafeCrawlTarget(f"Unable to resolve {hostname}") from exc
    for value in addresses:
        address = ipaddress.ip_address(value)
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
            raise UnsafeCrawlTarget("Private, local, link-local and reserved addresses are not allowed.")


def validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeCrawlTarget("Only absolute HTTP(S) URLs are allowed.")
    _assert_public_hostname(parsed.hostname)
    return url


def _hostname_key(hostname: str | None) -> str:
    value = (hostname or "").strip().lower().rstrip(".")
    return value[4:] if value.startswith("www.") else value


def _same_site(left: str | None, right: str | None) -> bool:
    return bool(left and right and _hostname_key(left) == _hostname_key(right))


def _site_root(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))


def _clean_candidate_url(url: str) -> str:
    value, _ = urldefrag(url)
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() not in _TRACKING_QUERY_KEYS
    ]
    path = parsed.path or "/"
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        path,
        "",
        urlencode(query, doseq=True),
        "",
    ))


def _looks_like_html_page(url: str) -> bool:
    parsed = urlparse(url)
    path = (parsed.path or "").casefold().rstrip("/")
    return not any(path.endswith(extension) for extension in _SKIP_EXTENSIONS)


def _is_priority_url(url: str) -> bool:
    path_tokens = {
        token.casefold()
        for token in urlparse(url).path.replace("_", "-").split("/")
        for token in token.split("-")
        if token
    }
    return bool(path_tokens.intersection(_PRIORITY_TOKENS))


def _alternate_site_roots(start_url: str) -> list[str]:
    parsed = urlparse(start_url)
    hostname = parsed.hostname or ""
    roots = [_site_root(start_url)]

    # Many official sites redirect between www and apex domains. Try both safely.
    if hostname.startswith("www."):
        alternate_host = hostname[4:]
    else:
        alternate_host = f"www.{hostname}"
    if parsed.port:
        alternate_host = f"{alternate_host}:{parsed.port}"
    alternate = urlunparse((parsed.scheme, alternate_host, "/", "", "", ""))
    if alternate not in roots:
        roots.append(alternate)
    return roots


def _seed_urls(start_url: str) -> list[str]:
    parsed = urlparse(start_url)
    requested = _clean_candidate_url(start_url)
    roots = _alternate_site_roots(start_url)
    seeds: list[str] = []

    # A configured deep URL may be outdated (for example /terms-and-conditions).
    # Prefer the official root first, while still attempting the configured URL.
    if parsed.path not in {"", "/"}:
        seeds.extend(roots)
        seeds.append(requested)
    else:
        seeds.append(requested)
        seeds.extend(roots)

    # Probe all useful paths on the configured host. For the www/apex alternate,
    # the root is enough because successful redirects and discovered links will
    # reveal the canonical host without doubling every request.
    primary_root = roots[0]
    for path in _PRIORITY_PATHS:
        candidate = urljoin(primary_root, f"{path}/" if path else "")
        seeds.append(_clean_candidate_url(candidate))

    return list(dict.fromkeys(candidate for candidate in seeds if candidate))


def safe_get(session: requests.Session, url: str, *, max_redirects: int = 5) -> requests.Response:
    current = validate_public_url(url)
    for _ in range(max_redirects + 1):
        response = session.get(
            current,
            timeout=settings.KNOWLEDGE_CRAWLER_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("location")
            if not location:
                response.raise_for_status()
            current = validate_public_url(urljoin(current, location))
            continue
        response.raise_for_status()
        return response
    raise UnsafeCrawlTarget("Too many redirects while crawling.")


def extract_page(url: str, response: requests.Response) -> CrawledPage:
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type.casefold() and "application/xhtml+xml" not in content_type.casefold():
        raise ValueError(f"Unsupported content type: {content_type}")
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "canvas"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)
    checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return CrawledPage(url=url, title=title[:500], text=text, html=response.text, checksum=checksum)


def _record_failure(diagnostics: MutableMapping[str, Any], url: str, exc: Exception) -> None:
    failures = diagnostics.setdefault("failed_urls", [])
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    failures.append({
        "url": url,
        "status_code": status_code,
        "error": exc.__class__.__name__,
    })
    diagnostics["failed_count"] = int(diagnostics.get("failed_count", 0)) + 1


def _enqueue_links(
    queue: deque[str],
    soup: BeautifulSoup,
    base_url: str,
    *,
    allowed_hostname: str,
    queued: set[str],
) -> None:
    priority: list[str] = []
    regular: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            continue
        candidate = _clean_candidate_url(urljoin(base_url, href))
        if not candidate or candidate in queued or not _looks_like_html_page(candidate):
            continue
        parsed = urlparse(candidate)
        if not _same_site(parsed.hostname, allowed_hostname):
            continue
        queued.add(candidate)
        (priority if _is_priority_url(candidate) else regular).append(candidate)

    # appendleft in reverse preserves the document order for high-value links.
    for candidate in reversed(priority):
        queue.appendleft(candidate)
    queue.extend(regular)


def _discover_sitemap_urls(
    session: requests.Session,
    roots: list[str],
    *,
    allowed_hostname: str,
    limit: int = 80,
    diagnostics: MutableMapping[str, Any],
) -> list[str]:
    discovered: list[str] = []
    sitemap_queue: deque[str] = deque()
    seen_sitemaps: set[str] = set()
    for root in roots:
        sitemap_queue.extend((urljoin(root, "/sitemap.xml"), urljoin(root, "/sitemap_index.xml")))

    while sitemap_queue and len(discovered) < limit and len(seen_sitemaps) < 8:
        sitemap_url = _clean_candidate_url(sitemap_queue.popleft())
        if not sitemap_url or sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap_url)
        try:
            response = safe_get(session, sitemap_url)
        except Exception:
            # Sitemaps are optional; do not pollute the public warning list.
            continue
        content_type = response.headers.get("content-type", "").casefold()
        if not any(token in content_type for token in ("xml", "text/plain", "text/html")):
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        for loc in soup.find_all("loc"):
            candidate = _clean_candidate_url(loc.get_text("", strip=True))
            if not candidate:
                continue
            parsed = urlparse(candidate)
            if not _same_site(parsed.hostname, allowed_hostname):
                continue
            if candidate.casefold().endswith(".xml"):
                if candidate not in seen_sitemaps:
                    sitemap_queue.append(candidate)
                continue
            if not _looks_like_html_page(candidate):
                continue
            discovered.append(candidate)
            if len(discovered) >= limit:
                break

    diagnostics["sitemap_urls_found"] = len(discovered)
    return list(dict.fromkeys(discovered))


def crawl_website(
    start_url: str,
    *,
    max_pages: int = 25,
    same_domain_only: bool = True,
    diagnostics: MutableMapping[str, Any] | None = None,
) -> list[CrawledPage]:
    """Crawl an official website without letting one broken URL stop the run.

    The configured URL may be a stale deep link. The crawler therefore tries the
    official root, common high-value sections, sitemap URLs and discovered links.
    Individual 404/410/403/timeout/content-type failures are recorded and skipped.
    """

    validate_public_url(start_url)
    requested = _clean_candidate_url(start_url)
    requested_host = urlparse(requested).hostname or ""
    crawl_diagnostics: MutableMapping[str, Any] = diagnostics if diagnostics is not None else {}
    crawl_diagnostics.clear()
    crawl_diagnostics.update({
        "requested_url": requested,
        "site_root": _site_root(requested),
        "effective_start_url": "",
        "fallback_used": False,
        "attempted_count": 0,
        "failed_count": 0,
        "failed_urls": [],
        "sitemap_urls_found": 0,
    })

    session = requests.Session()
    session.headers["User-Agent"] = settings.KNOWLEDGE_CRAWLER_USER_AGENT

    roots = _alternate_site_roots(requested)
    robots_url = urljoin(roots[0], "/robots.txt")
    robot = RobotFileParser(robots_url)
    try:
        robots_response = safe_get(session, robots_url)
        robot.parse(robots_response.text.splitlines())
    except Exception:
        robot = None

    seed_urls = _seed_urls(requested)
    sitemap_urls = _discover_sitemap_urls(
        session,
        roots,
        allowed_hostname=requested_host,
        diagnostics=crawl_diagnostics,
    )
    # Prioritize information-rich sitemap URLs, then all remaining ones.
    seed_urls.extend(sorted(sitemap_urls, key=lambda item: (not _is_priority_url(item), len(item))))
    seed_urls = list(dict.fromkeys(seed_urls))
    crawl_diagnostics["seed_count"] = len(seed_urls)

    queue: deque[str] = deque(seed_urls)
    queued: set[str] = set(seed_urls)
    visited: set[str] = set()
    pages: list[CrawledPage] = []
    page_checksums: set[str] = set()
    allowed_hostname = requested_host
    page_cap = min(max(1, int(max_pages)), int(settings.KNOWLEDGE_CRAWLER_MAX_PAGES))
    default_attempt_cap = max(20, page_cap * 3)
    attempt_cap = max(
        10,
        min(200, int(getattr(settings, "KNOWLEDGE_CRAWLER_MAX_ATTEMPTS", default_attempt_cap))),
    )
    crawl_diagnostics["attempt_cap"] = attempt_cap

    while queue and len(pages) < page_cap and int(crawl_diagnostics.get("attempted_count", 0)) < attempt_cap:
        current = _clean_candidate_url(queue.popleft())
        if not current or current in visited:
            continue
        visited.add(current)
        parsed = urlparse(current)
        if same_domain_only and not _same_site(parsed.hostname, allowed_hostname):
            continue
        if not _looks_like_html_page(current):
            continue
        try:
            validate_public_url(current)
        except Exception as exc:
            _record_failure(crawl_diagnostics, current, exc)
            continue
        if robot and not robot.can_fetch(settings.KNOWLEDGE_CRAWLER_USER_AGENT, current):
            crawl_diagnostics["robots_skipped_count"] = int(crawl_diagnostics.get("robots_skipped_count", 0)) + 1
            continue

        crawl_diagnostics["attempted_count"] = int(crawl_diagnostics.get("attempted_count", 0)) + 1
        try:
            response = safe_get(session, current)
            resolved_url = _clean_candidate_url(response.url or current) or current
            resolved_host = urlparse(resolved_url).hostname
            if same_domain_only and not _same_site(resolved_host, allowed_hostname):
                raise UnsafeCrawlTarget("Redirected outside the official website.")
            page = extract_page(resolved_url, response)
        except (requests.RequestException, UnsafeCrawlTarget, ValueError) as exc:
            _record_failure(crawl_diagnostics, current, exc)
            logger.info("Skipping unavailable organization page %s: %s", current, exc.__class__.__name__)
            continue

        if not crawl_diagnostics["effective_start_url"]:
            crawl_diagnostics["effective_start_url"] = page.url
            crawl_diagnostics["fallback_used"] = page.url.rstrip("/") != requested.rstrip("/")
        if page.text and page.checksum not in page_checksums:
            pages.append(page)
            page_checksums.add(page.checksum)

        soup = BeautifulSoup(response.text, "html.parser")
        _enqueue_links(
            queue,
            soup,
            page.url,
            allowed_hostname=allowed_hostname,
            queued=queued,
        )

    crawl_diagnostics["pages_collected"] = len(pages)
    crawl_diagnostics["attempt_limit_reached"] = bool(
        queue and int(crawl_diagnostics.get("attempted_count", 0)) >= attempt_cap
    )
    crawl_diagnostics["successful_urls"] = [page.url for page in pages]
    # Keep diagnostics compact before they are stored in JSON fields.
    crawl_diagnostics["failed_urls"] = list(crawl_diagnostics.get("failed_urls", []))[:25]
    return pages


SOCIAL_HOST_FIELDS = {
    "facebook.com": "facebook_url",
    "www.facebook.com": "facebook_url",
    "instagram.com": "instagram_url",
    "www.instagram.com": "instagram_url",
    "tiktok.com": "tiktok_url",
    "www.tiktok.com": "tiktok_url",
    "linkedin.com": "linkedin_url",
    "www.linkedin.com": "linkedin_url",
    "youtube.com": "youtube_url",
    "www.youtube.com": "youtube_url",
    "youtu.be": "youtube_url",
}


def discover_social_links(html_pages: list[CrawledPage]) -> dict[str, str]:
    discovered: dict[str, str] = {}
    for page in html_pages:
        soup = BeautifulSoup(page.html, "html.parser")
        for anchor in soup.find_all("a", href=True):
            candidate = urljoin(page.url, anchor["href"])
            parsed = urlparse(candidate)
            field = SOCIAL_HOST_FIELDS.get((parsed.hostname or "").lower())
            if field and field not in discovered:
                discovered[field] = candidate[:500]
    return discovered
