import json
import logging
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import login, logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.growth_ai.services import record_request_event
from .auth_services import (
    build_google_authorization_url,
    create_email_user,
    exchange_google_code,
    get_or_create_google_user,
)
from .forms import EmailLoginForm, EmailRegistrationForm
from .serializers import UserSerializer

logger = logging.getLogger(__name__)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


def _payload(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return {}


def _safe_next(request, value):
    value = (value or "/").strip()
    parsed = urlparse(value)
    allowed_hosts = {request.get_host(), *getattr(settings, "ALLOWED_HOSTS", [])}
    if parsed.netloc and parsed.netloc not in allowed_hosts:
        return "/"
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return "/"
    return value if value.startswith("/") else "/"


def _form_errors(form):
    return {field: [str(message) for message in errors] for field, errors in form.errors.items()}


@require_POST
def email_login(request):
    data = _payload(request)
    form = EmailLoginForm(data, request=request)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": _form_errors(form)}, status=400)
    user = form.get_user()
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.set_expiry(60 * 60 * 24 * 30 if form.cleaned_data.get("remember") else 0)
    record_request_event(request, "login", metadata={"method": "email"}, user=user)
    return JsonResponse({"ok": True, "redirect_url": _safe_next(request, data.get("next"))})


@require_POST
def email_register(request):
    data = _payload(request)
    form = EmailRegistrationForm(data)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": _form_errors(form)}, status=400)
    user = create_email_user(**form.cleaned_data)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    record_request_event(request, "register", metadata={"method": "email"}, user=user)
    return JsonResponse({"ok": True, "redirect_url": _safe_next(request, data.get("next"))}, status=201)


@require_POST
def session_logout(request):
    user = request.user if request.user.is_authenticated else None
    record_request_event(request, "logout", metadata={"method": "session"}, user=user)
    logout(request)
    return JsonResponse({"ok": True, "redirect_url": "/"})


@require_GET
def google_start(request):
    next_url = _safe_next(request, request.GET.get("next"))
    try:
        return redirect(build_google_authorization_url(request, next_url))
    except RuntimeError as exc:
        logger.warning("Google sign-in unavailable: %s", exc)
        return redirect(f"/?auth_error=google_not_configured")


@require_GET
def google_callback(request):
    expected_state = request.session.pop("google_auth_state", "")
    returned_state = request.GET.get("state", "")
    next_url = _safe_next(request, request.session.pop("google_auth_next", "/"))
    request.session.pop("google_auth_nonce", None)
    if not expected_state or expected_state != returned_state:
        return redirect("/?auth_error=invalid_google_state")
    if request.GET.get("error"):
        return redirect("/?auth_error=google_cancelled")
    code = request.GET.get("code")
    if not code:
        return redirect("/?auth_error=google_missing_code")
    try:
        profile = exchange_google_code(code)
        user, created = get_or_create_google_user(profile)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        record_request_event(
            request,
            "google_account_created" if created else "google_login",
            metadata={"method": "google"},
            user=user,
        )
        return redirect(next_url)
    except Exception:
        logger.exception("Google authentication callback failed")
        return redirect("/?auth_error=google_failed")
