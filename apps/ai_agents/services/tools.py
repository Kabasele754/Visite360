from __future__ import annotations

from dataclasses import asdict

from django.db.models import Count, Sum

from apps.knowledge.models import ServiceOffering
from apps.knowledge.services.search import semantic_search
from apps.vendors.models import AppointmentRequest, Order, Product


def knowledge_search(*, organization, query: str, limit: int = 6) -> dict:
    hits = semantic_search(organization=organization, query=query, limit=limit)
    return {"results": [asdict(hit) for hit in hits]}


def list_products(*, organization, limit: int = 20) -> dict:
    rows = Product.objects.filter(organization=organization, status=Product.Status.ACTIVE)[:limit]
    return {"products": [{"id": row.id, "name": row.name, "price": str(row.price), "currency": row.currency, "stock": row.stock_quantity, "slug": row.slug} for row in rows]}


def list_services(*, organization, limit: int = 20) -> dict:
    rows = ServiceOffering.objects.filter(organization=organization, is_active=True)[:limit]
    return {"services": [{"id": row.id, "name": row.name, "description": row.short_description, "price_from": str(row.price_from) if row.price_from is not None else None, "currency": row.currency, "booking_url": row.booking_url} for row in rows]}


def analytics_summary(*, organization) -> dict:
    orders = Order.objects.filter(organization=organization)
    appointments = AppointmentRequest.objects.filter(organization=organization)
    return {
        "orders": orders.aggregate(total=Count("id"), revenue=Sum("total")),
        "appointments": appointments.values("status").annotate(total=Count("id")).order_by("status"),
        "top_products": list(Product.objects.filter(organization=organization).order_by("-order_count").values("id", "name", "order_count", "view_count")[:10]),
    }


TOOL_REGISTRY = {
    "knowledge_search": knowledge_search,
    "list_products": list_products,
    "list_services": list_services,
    "analytics_summary": analytics_summary,
}
