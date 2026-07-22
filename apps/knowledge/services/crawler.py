from __future__ import annotations

import hashlib
import ipaddress
import socket
from collections import deque
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from django.conf import settings


class UnsafeCrawlTarget(ValueError):
    pass


@dataclass(slots=True)
class CrawledPage:
    url: str
    title: str
    text: str
    html: str
    checksum: str


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
    if "text/html" not in content_type:
        raise ValueError(f"Unsupported content type: {content_type}")
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "canvas"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)
    checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return CrawledPage(url=url, title=title[:500], text=text, html=response.text, checksum=checksum)


def crawl_website(start_url: str, *, max_pages: int = 25, same_domain_only: bool = True) -> list[CrawledPage]:
    validate_public_url(start_url)
    start = urlparse(start_url)
    session = requests.Session()
    session.headers["User-Agent"] = settings.KNOWLEDGE_CRAWLER_USER_AGENT
    robots_url = urljoin(start_url, "/robots.txt")
    robot = RobotFileParser(robots_url)
    try:
        robots_response = safe_get(session, robots_url)
        robot.parse(robots_response.text.splitlines())
    except Exception:
        robot = None

    queue = deque([start_url])
    visited: set[str] = set()
    pages: list[CrawledPage] = []
    while queue and len(pages) < min(max_pages, settings.KNOWLEDGE_CRAWLER_MAX_PAGES):
        current, _ = urldefrag(queue.popleft())
        if current in visited:
            continue
        visited.add(current)
        parsed = urlparse(current)
        if same_domain_only and parsed.hostname != start.hostname:
            continue
        validate_public_url(current)
        if robot and not robot.can_fetch(settings.KNOWLEDGE_CRAWLER_USER_AGENT, current):
            continue
        response = safe_get(session, current)
        page = extract_page(current, response)
        if page.text:
            pages.append(page)
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.find_all("a", href=True):
            candidate, _ = urldefrag(urljoin(current, anchor["href"]))
            candidate_parsed = urlparse(candidate)
            if candidate_parsed.scheme in {"http", "https"}:
                if not same_domain_only or candidate_parsed.hostname == start.hostname:
                    queue.append(candidate)
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
