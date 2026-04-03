from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.models import Organization
from apps.organizations.permissions import IsOrganizationMember

from .models import Place
from .serializers import PlaceSerializer, PublicPlaceSerializer
from .permissions import CanManageOrganizationPlace
from .services import (
    prepare_place_before_create,
    publish_place,
    archive_place,
    unpublish_place,
    generate_unique_place_slug,
)


class PublicPlaceListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicPlaceSerializer
    search_fields = ["name", "city", "category", "country"]
    ordering_fields = ["published_at", "name", "city", "created_at"]

    def get_queryset(self):
        queryset = Place.objects.filter(status=Place.Status.PUBLISHED).order_by("-published_at", "-created_at")

        category = self.request.query_params.get("category")
        city = self.request.query_params.get("city")
        country = self.request.query_params.get("country")

        if category:
            queryset = queryset.filter(category=category)
        if city:
            queryset = queryset.filter(city__iexact=city)
        if country:
            queryset = queryset.filter(country__iexact=country)

        return queryset


class PublicPlaceDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        place = get_object_or_404(
            Place,
            slug=slug,
            status=Place.Status.PUBLISHED,
        )
        return Response(PublicPlaceSerializer(place).data)


class OrgPlaceListCreateView(generics.ListCreateAPIView):
    serializer_class = PlaceSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get_queryset(self):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])
        return Place.objects.filter(organization=org).order_by("-created_at")

    def perform_create(self, serializer):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])

        validated_data = prepare_place_before_create(serializer.validated_data.copy())
        serializer.save(
            organization=org,
            **validated_data,
        )


class OrgPlaceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PlaceSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    lookup_field = "id"

    def get_queryset(self):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])
        return Place.objects.filter(organization=org)

    def perform_update(self, serializer):
        place = serializer.save()

        if not place.slug:
            place.slug = generate_unique_place_slug(place.name)
            place.save(update_fields=["slug", "updated_at"])


class PublishPlaceView(APIView):
    permission_classes = [IsAuthenticated, CanManageOrganizationPlace]

    def post(self, request, organization_slug, id):
        org = get_object_or_404(Organization, slug=organization_slug)
        place = get_object_or_404(Place, organization=org, id=id)

        publish_place(place)
        return Response(PlaceSerializer(place).data, status=status.HTTP_200_OK)


class UnpublishPlaceView(APIView):
    permission_classes = [IsAuthenticated, CanManageOrganizationPlace]

    def post(self, request, organization_slug, id):
        org = get_object_or_404(Organization, slug=organization_slug)
        place = get_object_or_404(Place, organization=org, id=id)

        unpublish_place(place)
        return Response(PlaceSerializer(place).data, status=status.HTTP_200_OK)


class ArchivePlaceView(APIView):
    permission_classes = [IsAuthenticated, CanManageOrganizationPlace]

    def post(self, request, organization_slug, id):
        org = get_object_or_404(Organization, slug=organization_slug)
        place = get_object_or_404(Place, organization=org, id=id)

        archive_place(place)
        return Response(PlaceSerializer(place).data, status=status.HTTP_200_OK)