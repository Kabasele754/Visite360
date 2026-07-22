from django.test import RequestFactory, SimpleTestCase, override_settings
from django.http import HttpResponse
from apps.monitoring.middleware import RequestTraceMiddleware


class TraceMiddlewareTests(SimpleTestCase):
    @override_settings(MONITORING_STORE_REQUEST_EVENTS=False)
    def test_adds_request_id(self):
        request = RequestFactory().get("/health/")
        response = RequestTraceMiddleware(lambda request: HttpResponse("ok"))(request)
        self.assertTrue(response["X-Request-ID"])
        self.assertIn("app;dur=", response["Server-Timing"])
