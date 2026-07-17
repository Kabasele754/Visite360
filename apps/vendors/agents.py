from __future__ import annotations

import json
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from .models import (
    AgentRunStatus,
    CustomerBehaviorEvent,
    IntelligentAgent,
    IntelligentAgentRun,
    IntelligentRecommendation,
    Order,
    Product,
)


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "title": {"type": "string"},
                    "rationale": {"type": "string"},
                    "action": {"type": "string"},
                    "impact": {"type": "string", "enum": ["low", "medium", "high"]},
                    "effort": {"type": "string", "enum": ["low", "medium", "high"]},
                    "priority": {"type": "integer", "minimum": 1, "maximum": 5},
                    "metadata": {"type": "object"},
                },
                "required": [
                    "category", "title", "rationale", "action",
                    "impact", "effort", "priority",
                ],
            },
        },
        "watch_metrics": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["summary", "recommendations", "watch_metrics"],
}


def build_agent_snapshot(organization):
    products = list(
        Product.objects.filter(organization=organization)
        .values(
            "id", "name", "currency", "price", "stock_quantity",
            "view_count", "order_count", "status", "is_featured",
            "delivery_available", "pickup_available",
        )[:250]
    )
    orders = organization.orders.exclude(status=Order.Status.CANCELLED)
    paid_orders = orders.filter(payment_status="paid")
    event_rows = (
        CustomerBehaviorEvent.objects.filter(organization=organization)
        .values("event_type")
        .annotate(total=Count("id"))
    )
    zones = list(
        organization.delivery_zones.filter(is_active=True)
        .values(
            "name", "country_code", "province", "cities", "currency",
            "fee", "free_delivery_threshold",
            "estimated_days_min", "estimated_days_max",
        )
    )
    sources = list(
        organization.market_sources.filter(is_active=True)
        .values("source_type", "label", "url", "metrics", "latest_summary")
    )
    paid_revenue = paid_orders.aggregate(value=Sum("total"))["value"] or Decimal("0.00")

    return {
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "slug": organization.slug,
        },
        "products": products,
        "delivery_zones": zones,
        "commerce": {
            "orders_total": orders.count(),
            "orders_paid": paid_orders.count(),
            "paid_revenue": str(paid_revenue),
            "average_order_value": str(
                paid_revenue / max(paid_orders.count(), 1)
            ),
        },
        "behavior_events": {
            row["event_type"]: row["total"]
            for row in event_rows
        },
        "appointments": {
            row["status"]: row["total"]
            for row in organization.appointment_requests.values("status").annotate(total=Count("id"))
        },
        "tours": {
            "count": organization.tours.count(),
        },
        "market_sources": sources,
    }


def _fallback_result(agent, snapshot):
    recommendations = []
    if agent.code == "delivery-optimizer":
        if not snapshot["delivery_zones"]:
            recommendations.append({
                "category": "delivery",
                "title": "Configure delivery zones",
                "rationale": "No active delivery zone is configured, so delivery pricing cannot be calculated reliably.",
                "action": "Create at least one South African delivery zone and define its fee, threshold and delivery time.",
                "impact": "high",
                "effort": "low",
                "priority": 1,
                "metadata": {},
            })
    low_stock = [
        p for p in snapshot["products"]
        if p["status"] == "active" and int(p["stock_quantity"] or 0) < 5
    ]
    if low_stock:
        recommendations.append({
            "category": "inventory",
            "title": "Review low-stock products",
            "rationale": f"{len(low_stock)} active products have fewer than five units available.",
            "action": "Restock, pause promotion or mark the affected products unavailable before running campaigns.",
            "impact": "high",
            "effort": "medium",
            "priority": 2,
            "metadata": {"product_ids": [item["id"] for item in low_stock[:20]]},
        })
    if not recommendations:
        recommendations.append({
            "category": "growth",
            "title": "Connect tours to measurable commerce actions",
            "rationale": "Twinscopes can measure product, cart, checkout, purchase and appointment events in one funnel.",
            "action": "Place one contextual product or appointment CTA in the highest-intent tour scenes and compare conversion weekly.",
            "impact": "high",
            "effort": "medium",
            "priority": 2,
            "metadata": {},
        })
    return {
        "summary": "A rules-based recommendation was generated because Gemini was unavailable.",
        "recommendations": recommendations,
        "watch_metrics": [
            "view_product",
            "add_to_cart",
            "begin_checkout",
            "purchase",
            "book_appointment",
        ],
    }


@transaction.atomic
def execute_agent_run(run_id):
    run = (
        IntelligentAgentRun.objects
        .select_for_update()
        .select_related("organization", "agent")
        .get(pk=run_id)
    )
    run.status = AgentRunStatus.RUNNING
    run.started_at = timezone.now()
    run.error = ""
    run.save(update_fields=["status", "started_at", "error", "updated_at"])

    snapshot = build_agent_snapshot(run.organization)
    run.input_snapshot = snapshot
    run.save(update_fields=["input_snapshot", "updated_at"])

    result = None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            vertexai=getattr(settings, "GOOGLE_GENAI_USE_VERTEXAI", True),
            project=getattr(settings, "GOOGLE_CLOUD_PROJECT", None),
            location=getattr(settings, "GOOGLE_CLOUD_LOCATION", "us-central1"),
        )
        prompt = (
            f"{run.agent.system_instruction}\n\n"
            "Analyze only the JSON snapshot below. Return a small set of practical recommendations. "
            "Every recommendation must include a measurable action and must not invent external metrics.\n\n"
            + json.dumps(snapshot, ensure_ascii=False, default=str)
        )
        response = client.models.generate_content(
            model=run.agent.model_name or getattr(settings, "GEMINI_MARKET_MODEL", "gemini-2.5-flash"),
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
                temperature=0.2,
            ),
        )
        result = json.loads(response.text)
    except Exception as exc:
        result = _fallback_result(run.agent, snapshot)
        run.error = str(exc)[:2000]

    IntelligentRecommendation.objects.filter(run=run).delete()
    for item in result.get("recommendations", [])[:12]:
        IntelligentRecommendation.objects.create(
            organization=run.organization,
            run=run,
            category=item.get("category", "growth")[:80],
            title=item.get("title", "Recommendation")[:220],
            rationale=item.get("rationale", ""),
            action=item.get("action", ""),
            impact=item.get("impact", "medium")[:20],
            effort=item.get("effort", "medium")[:20],
            priority=max(1, min(5, int(item.get("priority", 3)))),
            metadata=item.get("metadata", {}) or {},
        )

    run.output = result
    run.status = AgentRunStatus.COMPLETED
    run.completed_at = timezone.now()
    run.save(update_fields=[
        "output", "status", "completed_at", "error", "updated_at"
    ])
    return run
