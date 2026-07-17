from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger(__name__)
User = get_user_model()


def normalize_email(value: str) -> str:
    return User.objects.normalize_email((value or "").strip()).lower()


def _unique_username(email: str) -> str:
    base = (email.split("@", 1)[0] or "customer")[:120]
    candidate = base
    index = 0
    while User.objects.filter(username=candidate).exists():
        index += 1
        candidate = f"{base[:110]}-{index}"
    return candidate


def find_existing_customer(email: str):
    email = normalize_email(email)
    if not email:
        return None
    return User.objects.filter(email__iexact=email).first()


def attach_existing_customer(order):
    """Attach an existing account by email without authenticating the browser."""
    if order.customer_id:
        return order.customer
    user = find_existing_customer(order.customer_email)
    if user:
        order.customer = user
        order.save(update_fields=["customer", "updated_at"])
    return user


@dataclass
class ProvisionResult:
    user: object
    created: bool
    activation_sent: bool = False


@transaction.atomic
def provision_customer_after_payment(order, request=None) -> ProvisionResult:
    """
    Link a paid order to an existing account, or create a customer account.
    Never blocks or rolls back a successful payment because email delivery failed.
    """
    email = normalize_email(order.customer_email)
    if not email:
        raise ValueError("A customer email is required to create an account.")

    user = User.objects.select_for_update().filter(email__iexact=email).first()
    created = False
    if user is None:
        names = (order.customer_name or "").strip().split()
        user = User(
            email=email,
            username=_unique_username(email),
            first_name=names[0][:150] if names else "",
            last_name=" ".join(names[1:])[:150] if len(names) > 1 else "",
            phone=(order.customer_phone or "")[:32],
            is_customer=True,
        )
        user.set_unusable_password()
        user.save()
        created = True
    else:
        changed = []
        if not getattr(user, "is_customer", False):
            user.is_customer = True
            changed.append("is_customer")
        if not getattr(user, "phone", "") and order.customer_phone:
            user.phone = order.customer_phone[:32]
            changed.append("phone")
        if changed:
            user.save(update_fields=changed)

    if order.customer_id != user.id:
        order.customer = user
        order.save(update_fields=["customer", "updated_at"])

    activation_sent = False
    if created and request is not None:
        activation_sent = send_customer_activation(user, request)
    return ProvisionResult(user=user, created=created, activation_sent=activation_sent)


def send_customer_activation(user, request) -> bool:
    try:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        url = request.build_absolute_uri(
            reverse("vendors:customer_activate", kwargs={"uidb64": uid, "token": token})
        )
        subject = "Activate your Twinscopes customer account"
        message = (
            f"Hello {user.get_full_name() or user.email},\n\n"
            "Your order was received and a Twinscopes customer account was created for you.\n"
            f"Create your password and verify your email here:\n{url}\n\n"
            "You can then follow your orders and delivery status from your dashboard."
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
        return True
    except Exception:
        logger.exception("Customer activation email failed for user_id=%s", user.pk)
        return False


def apply_stripe_customer_id(user, stripe_customer_id: str) -> None:
    if not user or not stripe_customer_id:
        return
    if getattr(user, "stripe_customer_id", "") != stripe_customer_id:
        user.stripe_customer_id = stripe_customer_id
        user.save(update_fields=["stripe_customer_id"])
