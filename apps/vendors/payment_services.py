from __future__ import annotations

import base64
import logging
from decimal import Decimal, ROUND_HALF_UP

import requests
from django.conf import settings
from django.urls import reverse

from .customer_accounts import attach_existing_customer

logger = logging.getLogger(__name__)


class PaymentConfigurationError(RuntimeError):
    pass


def _minor_units(amount: Decimal, currency: str) -> int:
    zero_decimal = {
        "BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA", "PYG",
        "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF",
    }
    value = Decimal(amount)
    if currency.upper() in zero_decimal:
        return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def validate_stripe_configuration() -> None:
    secret = getattr(settings, "STRIPE_SECRET_KEY", "") or ""
    publishable = getattr(settings, "STRIPE_PUBLISHABLE_KEY", "") or ""
    mode = getattr(settings, "STRIPE_MODE", "test")
    if not secret or not publishable:
        raise PaymentConfigurationError("Stripe API keys are missing for the selected environment.")
    expected_secret = "sk_live_" if mode == "live" else "sk_test_"
    expected_public = "pk_live_" if mode == "live" else "pk_test_"
    if not secret.startswith(expected_secret) or not publishable.startswith(expected_public):
        raise PaymentConfigurationError(
            f"Stripe {mode} mode is selected, but the configured keys do not match that mode."
        )


def stripe_enabled() -> bool:
    try:
        validate_stripe_configuration()
        return True
    except PaymentConfigurationError:
        return False


def _stripe_line_items(order):
    items = [
        {
            "price_data": {
                "currency": order.currency.lower(),
                "product_data": {
                    "name": item.product_name,
                    "metadata": {"product_id": str(item.product_id)},
                },
                "unit_amount": _minor_units(item.unit_price, order.currency),
            },
            "quantity": item.quantity,
        }
        for item in order.items.all()
    ]
    if order.delivery_fee > 0:
        items.append(
            {
                "price_data": {
                    "currency": order.currency.lower(),
                    "product_data": {"name": "Delivery"},
                    "unit_amount": _minor_units(order.delivery_fee, order.currency),
                },
                "quantity": 1,
            }
        )
    return items


def create_stripe_embedded_checkout(request, order):
    """Create a current Stripe embedded-page Checkout Session and return its client secret."""
    import stripe

    validate_stripe_configuration()
    stripe.api_key = settings.STRIPE_SECRET_KEY
    attach_existing_customer(order)

    params = {
        "ui_mode": "embedded_page",
        "mode": "payment",
        "client_reference_id": order.reference,
        "line_items": _stripe_line_items(order),
        "return_url": request.build_absolute_uri(
            reverse("vendors:stripe_success", kwargs={"reference": order.reference})
        ) + "?session_id={CHECKOUT_SESSION_ID}",
        "metadata": {
            "order_reference": order.reference,
            "organization_id": str(order.organization_id),
        },
        "payment_intent_data": {
            "metadata": {"order_reference": order.reference}
        },
        "billing_address_collection": "auto",
        "phone_number_collection": {"enabled": True},
        "allow_promotion_codes": True,
        "locale": "auto",
        "customer_creation": "always",
    }

    stripe_customer_id = getattr(order.customer, "stripe_customer_id", "") if order.customer_id else ""
    if stripe_customer_id:
        params.pop("customer_creation", None)
        params["customer"] = stripe_customer_id
    elif order.customer_email:
        params["customer_email"] = order.customer_email

    try:
        session = stripe.checkout.Session.create(**params)
    except stripe.error.AuthenticationError as exc:
        logger.exception("Stripe authentication failed")
        raise PaymentConfigurationError(
            "Stripe rejected the API key. Verify that the selected test/live keys match STRIPE_MODE."
        ) from exc
    except stripe.error.InvalidRequestError as exc:
        logger.exception("Stripe embedded checkout request invalid")
        raise PaymentConfigurationError(
            f"Stripe embedded checkout configuration error: {exc.user_message or str(exc)}"
        ) from exc
    except stripe.error.StripeError as exc:
        logger.exception("Stripe embedded checkout failed")
        raise RuntimeError(exc.user_message or "Stripe could not initialise the embedded payment form.") from exc

    order.stripe_checkout_session_id = session.id
    order.payment_provider = "stripe"
    order.payment_error = ""
    order.save(update_fields=[
        "stripe_checkout_session_id",
        "payment_provider",
        "payment_error",
        "updated_at",
    ])
    return session.client_secret


def _paypal_access_token():
    if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_SECRET:
        raise PaymentConfigurationError("PayPal is not configured.")
    token = base64.b64encode(
        f"{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_SECRET}".encode()
    ).decode()
    response = requests.post(
        f"{settings.PAYPAL_API_BASE_URL}/v1/oauth2/token",
        headers={"Authorization": f"Basic {token}", "Accept": "application/json"},
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def create_paypal_order_for_sdk(order):
    """Create an Orders v2 order for the PayPal JS SDK and return the order ID."""
    token = _paypal_access_token()
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": order.reference,
                "custom_id": order.reference,
                "description": f"Twinscopes order {order.reference}",
                "amount": {
                    "currency_code": order.currency.upper(),
                    "value": f"{order.total:.2f}",
                    "breakdown": {
                        "item_total": {
                            "currency_code": order.currency.upper(),
                            "value": f"{order.subtotal:.2f}",
                        },
                        "shipping": {
                            "currency_code": order.currency.upper(),
                            "value": f"{order.delivery_fee:.2f}",
                        },
                    },
                },
                "items": [
                    {
                        "name": item.product_name[:127],
                        "quantity": str(item.quantity),
                        "unit_amount": {
                            "currency_code": order.currency.upper(),
                            "value": f"{item.unit_price:.2f}",
                        },
                        "category": "PHYSICAL_GOODS",
                    }
                    for item in order.items.all()
                ],
            }
        ],
        "application_context": {
            "brand_name": "Twinscopes",
            "shipping_preference": "NO_SHIPPING",
            "user_action": "PAY_NOW",
        },
    }
    response = requests.post(
        f"{settings.PAYPAL_API_BASE_URL}/v2/checkout/orders",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": f"create-{order.reference}",
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    order.paypal_order_id = data["id"]
    order.payment_provider = "paypal"
    order.payment_error = ""
    order.save(update_fields=[
        "paypal_order_id", "payment_provider", "payment_error", "updated_at"
    ])
    return data["id"]


def capture_paypal_order(order, paypal_order_id=None):
    token = _paypal_access_token()
    order_id = paypal_order_id or order.paypal_order_id
    if not order_id:
        raise PaymentConfigurationError("PayPal order ID is missing.")
    response = requests.post(
        f"{settings.PAYPAL_API_BASE_URL}/v2/checkout/orders/{order_id}/capture",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": f"capture-{order.reference}",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
