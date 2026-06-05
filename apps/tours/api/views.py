import hashlib
import uuid

from django.db import transaction
from django.db.models import Count, F, Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.models import Organization
from apps.places.models import Place
from apps.tours.models import Hotspot, Scene360, Tour, TourShare, TourUniqueView
from .serializers import ScenePublicSerializer, TourCardSerializer, TourDetailSerializer


class PublicTourPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 60

    def get_paginated_response(self, data):
        return Response(
            {
                "page": self.page.number,
                "page_size": self.get_page_size(self.request) or self.page_size,
                "total_count": self.page.paginator.count,
                "has_more": self.page.has_next(),
                "results": data,
            }
        )


class PublicTourQueryMixin:
    def get_queryset(self):
        qs = (
            Tour.objects.select_related("organization", "place")
            .filter(
                status=Tour.Status.PUBLISHED,
                organization__status=Organization.Status.ACTIVE,
                place__status=Place.Status.PUBLISHED,
            )
            .annotate(
                scene_count=Count(
                    "scenes",
                    filter=Q(
                        scenes__status=Scene360.Status.PUBLISHED,
                        scenes__is_public=True,
                    ),
                    distinct=True,
                ),
                unique_view_count=Count("unique_views", distinct=True),
                share_count=Count("shares", distinct=True),
            )
            .order_by("-is_featured", "-published_at", "-created_at")
        )

        q = (self.request.query_params.get("q") or "").strip()
        category = (self.request.query_params.get("category") or "").strip()
        city = (self.request.query_params.get("city") or "").strip()
        featured = (self.request.query_params.get("featured") or "").strip().lower()

        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(place__name__icontains=q)
                | Q(place__city__icontains=q)
                | Q(place__country__icontains=q)
            )

        if category:
            qs = qs.filter(place__category=category)

        if city:
            qs = qs.filter(place__city__iexact=city)

        if featured in {"1", "true", "yes"}:
            qs = qs.filter(is_featured=True)

        return qs


def public_scene_queryset():
    return (
        Scene360.objects.filter(status=Scene360.Status.PUBLISHED, is_public=True)
        .prefetch_related(
            Prefetch(
                "hotspots",
                queryset=Hotspot.objects.select_related("target_scene").order_by("id"),
            )
        )
        .order_by("order", "id")
    )


class PublicTourListAPIView(PublicTourQueryMixin, ListAPIView):
    serializer_class = TourCardSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = PublicTourPagination


class PublicTourDetailAPIView(PublicTourQueryMixin, RetrieveAPIView):
    serializer_class = TourDetailSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            Prefetch("scenes", queryset=public_scene_queryset()),
            "photos",
        )

    def get_object(self):
        return get_object_or_404(
            self.get_queryset(),
            organization__slug=self.kwargs["organization_slug"],
            id=self.kwargs["tour_id"],
        )


class PublicTourHeroAPIView(PublicTourQueryMixin, APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        base_qs = self.get_queryset().prefetch_related(Prefetch("scenes", queryset=public_scene_queryset()))
        tour = base_qs.filter(is_featured=True).first() or base_qs.first()

        if not tour:
            return Response(
                {"detail": "No published tour found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(TourDetailSerializer(tour, context={"request": request}).data)


class PublicTourScenesAPIView(PublicTourQueryMixin, APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, organization_slug, tour_id, *args, **kwargs):
        tour = get_object_or_404(
            self.get_queryset(),
            organization__slug=organization_slug,
            id=tour_id,
        )
        scenes = public_scene_queryset().filter(tour=tour)
        return Response(
            {
                "tour_id": tour.id,
                "organization_slug": tour.organization.slug,
                "count": scenes.count(),
                "results": ScenePublicSerializer(
                    scenes,
                    many=True,
                    context={"request": request},
                ).data,
            }
        )


class PublicTourSceneDetailAPIView(PublicTourQueryMixin, APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, organization_slug, tour_id, scene_id, *args, **kwargs):
        tour = get_object_or_404(
            self.get_queryset(),
            organization__slug=organization_slug,
            id=tour_id,
        )
        scene = get_object_or_404(public_scene_queryset(), tour=tour, scene_id=scene_id)
        return Response(ScenePublicSerializer(scene, context={"request": request}).data)


def _hash_value(value):
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest() if value else ""


def _get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")


def _get_or_create_visitor_key(request):
    if request.user and request.user.is_authenticated:
        return f"user:{request.user.pk}", False

    body_key = str(request.data.get("visitor_key") or "").strip() if isinstance(request.data, dict) else ""
    header_key = str(request.headers.get("X-Visitor-Key") or "").strip()
    cookie_key = str(request.COOKIES.get("vtour_visitor_id") or "").strip()

    if body_key:
        return body_key, False
    if header_key:
        return header_key, False
    if cookie_key:
        return cookie_key, False

    return f"anon:{uuid.uuid4().hex}", True


class PublicTourEngagementAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, organization_slug, tour_id, *args, **kwargs):
        tour = get_object_or_404(
            Tour.objects.select_related("organization", "place"),
            organization__slug=organization_slug,
            id=tour_id,
            status=Tour.Status.PUBLISHED,
            organization__status=Organization.Status.ACTIVE,
            place__status=Place.Status.PUBLISHED,
        )

        action = str(request.data.get("action") or "view").strip().lower()
        channel = str(request.data.get("channel") or TourShare.Channel.OTHER).strip().lower()
        visitor_key, new_key = _get_or_create_visitor_key(request)
        user = request.user if request.user.is_authenticated else None
        ip_hash = _hash_value(_get_client_ip(request))
        ua_hash = _hash_value(request.META.get("HTTP_USER_AGENT", ""))

        with transaction.atomic():
            if action == "view":
                _, created = TourUniqueView.objects.get_or_create(
                    tour=tour,
                    visitor_key=visitor_key,
                    defaults={
                        "user": user,
                        "ip_hash": ip_hash,
                        "user_agent_hash": ua_hash,
                    },
                )
                if created:
                    Tour.objects.filter(pk=tour.pk).update(view_count=F("view_count") + 1)

            elif action == "share":
                allowed = {choice[0] for choice in TourShare.Channel.choices}
                if channel not in allowed:
                    channel = TourShare.Channel.OTHER

                TourShare.objects.create(
                    tour=tour,
                    user=user,
                    visitor_key=visitor_key,
                    channel=channel,
                    ip_hash=ip_hash,
                    user_agent_hash=ua_hash,
                )

            else:
                return Response(
                    {"detail": "Invalid action. Use view or share."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        tour.refresh_from_db(fields=["view_count"])
        payload = {
            "ok": True,
            "action": action,
            "visitor_key": visitor_key,
            "view_count": tour.view_count,
            "unique_view_count": tour.unique_views.count(),
            "share_count": tour.shares.count(),
        }

        response = Response(payload)
        if new_key:
            response.set_cookie(
                "vtour_visitor_id",
                visitor_key,
                max_age=60 * 60 * 24 * 365,
                httponly=True,
                samesite="Lax",
            )
        return response
