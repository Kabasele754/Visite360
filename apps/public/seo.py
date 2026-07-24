from __future__ import annotations

from datetime import datetime
from xml.sax.saxutils import escape

from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.organizations.models import Organization
from apps.places.models import Place
from apps.tours.models import Tour
from apps.vendors.models import Product


XML_HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n'
SITEMAP_NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
IMAGE_SITEMAP_NS = 'http://www.google.com/schemas/sitemap-image/1.1'


def _absolute(request, path: str) -> str:
    return request.build_absolute_uri(path)


def _iso(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return value.isoformat()


def _url_entry(
    *,
    loc: str,
    lastmod=None,
    changefreq="weekly",
    priority="0.7",
    image_url: str = "",
    image_title: str = "",
) -> str:
    parts = ["  <url>", f"    <loc>{escape(loc)}</loc>"]
    if lastmod:
        parts.append(f"    <lastmod>{escape(_iso(lastmod))}</lastmod>")
    if changefreq:
        parts.append(f"    <changefreq>{escape(changefreq)}</changefreq>")
    if priority:
        parts.append(f"    <priority>{escape(str(priority))}</priority>")
    if image_url:
        parts.extend([
            "    <image:image>",
            f"      <image:loc>{escape(image_url)}</image:loc>",
            *([f"      <image:title>{escape(image_title)}</image:title>"] if image_title else []),
            "    </image:image>",
        ])
    parts.append("  </url>")
    return "\n".join(parts)


@require_GET
def sitemap_index(request):
    maps = [
        ("sitemap-static", "sitemap-static.xml"),
        ("sitemap-products", "sitemap-products.xml"),
        ("sitemap-tours", "sitemap-tours.xml"),
    ]
    rows = []
    for _, path in maps:
        rows.append(
            "  <sitemap>\n"
            f"    <loc>{escape(_absolute(request, '/' + path))}</loc>\n"
            "  </sitemap>"
        )
    xml = XML_HEADER + f'<sitemapindex xmlns="{SITEMAP_NS}">\n' + "\n".join(rows) + "\n</sitemapindex>\n"
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")


@require_GET
def static_sitemap(request):
    named_urls = [
        ("public_home", "daily", "1.0"),
        ("vendors:product_list", "daily", "0.9"),
        ("public_services", "monthly", "0.7"),
        ("public_about", "monthly", "0.6"),
        ("public_contact", "monthly", "0.5"),
        ("public-tours-map", "weekly", "0.8"),
    ]
    rows = []
    for name, frequency, priority in named_urls:
        try:
            path = reverse(name)
        except Exception:
            continue
        rows.append(_url_entry(loc=_absolute(request, path), changefreq=frequency, priority=priority))
    xml = XML_HEADER + f'<urlset xmlns="{SITEMAP_NS}">\n' + "\n".join(rows) + "\n</urlset>\n"
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")


@require_GET
def product_sitemap(request):
    products = (
        Product.objects.select_related("organization")
        .filter(
            status=Product.Status.ACTIVE,
            organization__status=Organization.Status.ACTIVE,
        )
        .only("slug", "updated_at", "organization__slug")
        .order_by("pk")
    )
    rows = []
    for product in products.iterator(chunk_size=1000):
        path = reverse(
            "vendors:product_detail",
            kwargs={
                "organization_slug": product.organization.slug,
                "product_slug": product.slug,
            },
        )
        rows.append(
            _url_entry(
                loc=_absolute(request, path),
                lastmod=product.updated_at,
                changefreq="weekly",
                priority="0.8",
            )
        )
    xml = XML_HEADER + f'<urlset xmlns="{SITEMAP_NS}">\n' + "\n".join(rows) + "\n</urlset>\n"
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")


@require_GET
def tour_sitemap(request):
    tours = (
        Tour.objects.select_related("organization")
        .filter(
            status=Tour.Status.PUBLISHED,
            organization__status=Organization.Status.ACTIVE,
            place__status=Place.Status.PUBLISHED,
        )
        .only("id", "title", "updated_at", "is_featured", "thumbnail_image", "organization__slug")
        .order_by("pk")
    )
    rows = []
    for tour in tours.iterator(chunk_size=1000):
        try:
            path = reverse(
                "tour-preview-public",
                kwargs={"organization_slug": tour.organization.slug, "tour_id": tour.id},
            )
        except Exception:
            path = f"/{tour.organization.slug}/tours/{tour.id}/preview/"
        image_url = ""
        try:
            if tour.thumbnail_image:
                image_url = _absolute(request, tour.thumbnail_image.url)
        except (AttributeError, ValueError):
            image_url = ""
        rows.append(
            _url_entry(
                loc=_absolute(request, path),
                lastmod=tour.updated_at,
                changefreq="weekly",
                priority="0.85" if tour.is_featured else "0.75",
                image_url=image_url,
                image_title=f"{tour.title} 360° virtual tour" if image_url else "",
            )
        )
    xml = (
        XML_HEADER
        + f'<urlset xmlns="{SITEMAP_NS}" xmlns:image="{IMAGE_SITEMAP_NS}">\n'
        + "\n".join(rows)
        + "\n</urlset>\n"
    )
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")


@require_GET
def robots_txt(request):
    sitemap_url = _absolute(request, reverse("sitemap-index"))
    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin/",
            "Disallow: /dashboard/",
            "Disallow: /api/",
            "Disallow: /cart/",
            "Disallow: /checkout/",
            "Disallow: /orders/",
            "Disallow: /*?*page=",
            "",
            f"Sitemap: {sitemap_url}",
            "",
        ]
    )
    return HttpResponse(body, content_type="text/plain; charset=utf-8")
