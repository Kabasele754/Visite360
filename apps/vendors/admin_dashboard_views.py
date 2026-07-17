from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.organizations.models import Organization
from .models import (
    BackInStockSubscription,
    CustomerNotification,
    DeliveryZone,
    IntelligentRecommendation,
    Order,
    Product,
    ProductCategory,
    ProductRecommendation,
    ProductReview,
    StockReservation,
    WebVitalMeasurement,
)


@staff_member_required
def marketplace_admin_home(request):
    orders = Order.objects.select_related("organization")
    products = Product.objects.select_related("organization", "category")
    reviews = ProductReview.objects.select_related("product", "customer")

    stats = {
        "organizations": Organization.objects.count(),
        "products": products.count(),
        "active_products": products.filter(status=Product.Status.ACTIVE).count(),
        "orders": orders.count(),
        "revenue": orders.exclude(status=Order.Status.CANCELLED).aggregate(total=Sum("total"))["total"] or 0,
        "pending_reviews": reviews.filter(status=ProductReview.Status.PENDING).count(),
        "low_stock": products.filter(track_inventory=True, stock_quantity__lte=5).count(),
        "delivery_zones": DeliveryZone.objects.filter(is_active=True).count(),
    }
    return render(request, "dashboard/marketplace_admin/home.html", {
        "stats": stats,
        "latest_products": products.order_by("-created_at")[:8],
        "latest_orders": orders.order_by("-created_at")[:8],
        "latest_reviews": reviews.order_by("-created_at")[:6],
        "current_organization": None,
    })


@staff_member_required
def marketplace_admin_products(request):
    products = Product.objects.select_related("organization", "category")
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    organization = request.GET.get("organization", "").strip()
    category = request.GET.get("category", "").strip()

    if q:
        products = products.filter(
            Q(name__icontains=q)
            | Q(sku__icontains=q)
            | Q(organization__name__icontains=q)
        )
    if status:
        products = products.filter(status=status)
    if organization:
        products = products.filter(organization__slug=organization)
    if category:
        products = products.filter(category__slug=category)

    paginator = Paginator(products.order_by("-created_at"), 30)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    return render(request, "dashboard/marketplace_admin/products.html", {
        "products": page_obj.object_list,
        "page_obj": page_obj,
        "organizations": Organization.objects.order_by("name"),
        "categories": ProductCategory.objects.order_by("name"),
        "status_choices": Product.Status.choices,
        "selected_q": q,
        "selected_status": status,
        "selected_organization": organization,
        "selected_category": category,
        "current_organization": None,
    })


@staff_member_required
@require_POST
def marketplace_admin_product_action(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    action = request.POST.get("action")

    if action == "toggle_featured":
        product.is_featured = not product.is_featured
        product.save(update_fields=["is_featured", "updated_at"])
        messages.success(request, f"Featured state updated for {product.name}.")
    elif action in dict(Product.Status.choices):
        product.status = action
        product.save(update_fields=["status", "updated_at"])
        messages.success(request, f"{product.name} changed to {product.get_status_display()}.")
    else:
        messages.error(request, "Unsupported product action.")

    return redirect(request.POST.get("next") or "vendors:marketplace_admin_products")


@staff_member_required
def marketplace_admin_categories(request):
    categories = ProductCategory.objects.annotate(
        product_total=Count("products"),
        active_product_total=Count(
            "products",
            filter=Q(products__status=Product.Status.ACTIVE),
        ),
    ).order_by("name")
    return render(request, "dashboard/marketplace_admin/categories.html", {
        "categories": categories,
        "editing": None,
        "current_organization": None,
    })


@staff_member_required
def marketplace_admin_category_form(request, category_id=None):
    category = get_object_or_404(ProductCategory, pk=category_id) if category_id else None
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        slug = (request.POST.get("slug") or slugify(name)).strip()
        if not name or not slug:
            messages.error(request, "Name and slug are required.")
        elif ProductCategory.objects.exclude(pk=getattr(category, "pk", None)).filter(slug=slug).exists():
            messages.error(request, "This category slug already exists.")
        else:
            item = category or ProductCategory()
            item.name = name
            item.slug = slug
            item.description = (request.POST.get("description") or "").strip()
            item.icon = (request.POST.get("icon") or "").strip()
            item.is_active = request.POST.get("is_active") == "on"
            item.save()
            messages.success(request, "Category saved.")
            return redirect("vendors:marketplace_admin_categories")

    categories = ProductCategory.objects.annotate(product_total=Count("products")).order_by("name")
    return render(request, "dashboard/marketplace_admin/categories.html", {
        "categories": categories,
        "editing": category,
        "current_organization": None,
    })


@staff_member_required
def marketplace_admin_orders(request):
    orders = Order.objects.select_related("organization", "customer")
    status = request.GET.get("status", "").strip()
    q = request.GET.get("q", "").strip()
    if status:
        orders = orders.filter(status=status)
    if q:
        orders = orders.filter(
            Q(reference__icontains=q)
            | Q(customer_name__icontains=q)
            | Q(customer_email__icontains=q)
            | Q(organization__name__icontains=q)
        )
    page_obj = Paginator(orders.order_by("-created_at"), 30).get_page(request.GET.get("page") or 1)
    return render(request, "dashboard/marketplace_admin/orders.html", {
        "orders": page_obj.object_list,
        "page_obj": page_obj,
        "status_choices": Order.Status.choices,
        "selected_status": status,
        "selected_q": q,
        "current_organization": None,
    })


@staff_member_required
def marketplace_admin_reviews(request):
    reviews = ProductReview.objects.select_related(
        "product", "product__organization", "customer", "order_item__order"
    )
    status = request.GET.get("status", "").strip()
    if status:
        reviews = reviews.filter(status=status)
    return render(request, "dashboard/marketplace_admin/reviews.html", {
        "reviews": reviews.order_by("-created_at")[:100],
        "status_choices": ProductReview.Status.choices,
        "selected_status": status,
        "current_organization": None,
    })


@staff_member_required
@require_POST
def marketplace_admin_review_action(request, review_id):
    review = get_object_or_404(ProductReview, pk=review_id)
    status = request.POST.get("status")
    if status in dict(ProductReview.Status.choices):
        review.status = status
        review.save(update_fields=["status", "updated_at"])
        messages.success(request, "Review moderation updated.")
    else:
        messages.error(request, "Invalid review status.")
    return redirect("vendors:marketplace_admin_reviews")


@staff_member_required
def marketplace_admin_system(request):
    return render(request, "dashboard/marketplace_admin/system.html", {
        "recommendations": ProductRecommendation.objects.select_related(
            "organization", "source_product", "recommended_product"
        ).order_by("-created_at")[:50],
        "agent_recommendations": IntelligentRecommendation.objects.select_related(
            "organization", "run", "run__agent"
        ).order_by("-created_at")[:50],
        "stock_reservations": StockReservation.objects.select_related(
            "product", "order"
        ).order_by("-created_at")[:50],
        "stock_subscriptions": BackInStockSubscription.objects.select_related(
            "product", "user"
        ).order_by("-created_at")[:50],
        "notifications": CustomerNotification.objects.select_related(
            "user", "order", "product"
        ).order_by("-created_at")[:50],
        "web_vitals": WebVitalMeasurement.objects.values("name").annotate(
            average=Avg("value"),
            total=Count("id"),
        ).order_by("name"),
        "current_organization": None,
    })
