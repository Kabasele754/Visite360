from __future__ import annotations

from unittest.mock import patch

import requests
from django.test import SimpleTestCase, override_settings

from apps.knowledge.services.crawler import crawl_website


class _FakeResponse:
    def __init__(self, url: str, *, status: int = 200, text: str = "", content_type: str = "text/html"):
        self.url = url
        self.status_code = status
        self.text = text
        self.headers = {"content-type": content_type}
        self.is_redirect = status in {301, 302, 303, 307, 308}
        self.is_permanent_redirect = status in {301, 308}

    def raise_for_status(self):
        if self.status_code >= 400:
            exc = requests.HTTPError(f"{self.status_code} for {self.url}")
            exc.response = self
            raise exc


class _FakeSession:
    def __init__(self, routes):
        self.routes = routes
        self.headers = {}

    def get(self, url, **kwargs):
        return self.routes.get(url, _FakeResponse(url, status=404, text="Not found"))


@override_settings(
    KNOWLEDGE_CRAWLER_USER_AGENT="TwinscopesTest/1.0",
    KNOWLEDGE_CRAWLER_TIMEOUT_SECONDS=2,
    KNOWLEDGE_CRAWLER_MAX_PAGES=20,
    KNOWLEDGE_CRAWLER_MAX_ATTEMPTS=30,
)
class ResilientOrganizationCrawlerTests(SimpleTestCase):
    @patch("apps.knowledge.services.crawler._assert_public_hostname", return_value=None)
    def test_broken_configured_page_recovers_from_home_and_about(self, _dns):
        routes = {
            "https://www.example.com/": _FakeResponse(
                "https://www.example.com/",
                text=(
                    "<html><title>Home</title><body><main>Official home page.</main>"
                    '<a href="/about/">About</a></body></html>'
                ),
            ),
            "https://www.example.com/about/": _FakeResponse(
                "https://www.example.com/about/",
                text="<html><title>About</title><body><main>About the organization.</main></body></html>",
            ),
            "https://www.example.com/terms-and-conditions": _FakeResponse(
                "https://www.example.com/terms-and-conditions",
                status=404,
            ),
        }
        diagnostics = {}
        with patch("apps.knowledge.services.crawler.requests.Session", return_value=_FakeSession(routes)):
            pages = crawl_website(
                "https://www.example.com/terms-and-conditions",
                max_pages=2,
                diagnostics=diagnostics,
            )

        self.assertEqual([page.title for page in pages], ["Home", "About"])
        self.assertTrue(diagnostics["fallback_used"])
        self.assertEqual(diagnostics["effective_start_url"], "https://www.example.com/")

    @patch("apps.knowledge.services.crawler._assert_public_hostname", return_value=None)
    def test_common_about_path_is_tried_when_home_is_missing(self, _dns):
        routes = {
            "https://www.example.org/about/": _FakeResponse(
                "https://www.example.org/about/",
                text="<html><title>About Org</title><body><main>Public organization details.</main></body></html>",
            ),
        }
        diagnostics = {}
        with patch("apps.knowledge.services.crawler.requests.Session", return_value=_FakeSession(routes)):
            pages = crawl_website(
                "https://www.example.org/old-page",
                max_pages=1,
                diagnostics=diagnostics,
            )

        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].url, "https://www.example.org/about/")
        self.assertGreaterEqual(diagnostics["failed_count"], 1)
