from __future__ import annotations

import hashlib
from django.core.exceptions import ValidationError
from apps.integrations.models import DynamicForm, FormSubmission


def validate_submission(form: DynamicForm, data: dict) -> dict:
    cleaned = {}
    errors = {}
    for field in form.fields.all():
        value = data.get(field.key)
        if field.is_required and (value is None or value == "" or value == []):
            errors[field.key] = "This field is required."
            continue
        if value is None:
            continue
        if field.field_type == "email" and "@" not in str(value):
            errors[field.key] = "Enter a valid email address."
        elif field.field_type == "number":
            try:
                value = float(value)
            except (TypeError, ValueError):
                errors[field.key] = "Enter a valid number."
        elif field.field_type in {"select", "multiselect"} and field.options:
            allowed = {str(option.get("value", option)) if isinstance(option, dict) else str(option) for option in field.options}
            selected = value if isinstance(value, list) else [value]
            if any(str(item) not in allowed for item in selected):
                errors[field.key] = "Select a valid option."
        cleaned[field.key] = value
    if errors:
        raise ValidationError(errors)
    return cleaned


def create_submission(*, form: DynamicForm, data: dict, request=None, user=None) -> FormSubmission:
    cleaned = validate_submission(form, data)
    ip_hash = ""
    user_agent = ""
    source_url = ""
    if request is not None:
        ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "")).split(",")[0].strip()
        if ip:
            ip_hash = hashlib.sha256(ip.encode("utf-8")).hexdigest()
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
        source_url = request.data.get("source_url", "") if hasattr(request, "data") else ""
    return FormSubmission.objects.create(
        form=form,
        user=user if getattr(user, "is_authenticated", False) else None,
        data=cleaned,
        source_url=source_url,
        visitor_id=str(data.get("visitor_id", ""))[:120],
        ip_hash=ip_hash,
        user_agent=user_agent,
    )
