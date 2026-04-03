from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.models import Organization
from apps.organizations.permissions import IsOrganizationMember
from apps.places.models import Place

from apps.tours.models import Tour, Scene360, Hotspot, TourPhoto
from apps.tours.serializers import (
    TourSerializer,
    PublicTourSerializer,
    Scene360Serializer,
    HotspotSerializer,
    TourPhotoSerializer,
)
from apps.tours.services import (
    prepare_tour_before_create,
    build_tour_manifest,
    publish_tour,
    unpublish_tour,
    increment_tour_views,
)


class PublicPlaceTourView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        place = get_object_or_404(
            Place,
            slug=slug,
            status=Place.Status.PUBLISHED,
        )

        tour = place.tours.filter(status=Tour.Status.PUBLISHED).order_by("-version", "-created_at").first()

        if not tour:
            return Response(
                {"detail": "No published tour found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        increment_tour_views(tour)
        return Response(PublicTourSerializer(tour).data)


class OrgTourListCreateView(generics.ListCreateAPIView):
    serializer_class = TourSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get_queryset(self):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])
        return Tour.objects.filter(
            organization=org
        ).select_related("place").prefetch_related("scenes", "photos").order_by("-created_at")

    def perform_create(self, serializer):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])
        place = get_object_or_404(
            Place,
            id=self.request.data.get("place"),
            organization=org,
        )

        validated_data = prepare_tour_before_create(serializer.validated_data.copy())
        serializer.save(
            organization=org,
            place=place,
            **validated_data,
        )


class OrgTourDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TourSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    lookup_field = "id"

    def get_queryset(self):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])
        return Tour.objects.filter(
            organization=org
        ).select_related("place").prefetch_related("scenes", "photos")


class PublishTourView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def post(self, request, organization_slug, id):
        org = get_object_or_404(Organization, slug=organization_slug)
        tour = get_object_or_404(Tour, organization=org, id=id)

        publish_tour(tour)
        return Response(TourSerializer(tour).data, status=status.HTTP_200_OK)


class UnpublishTourView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def post(self, request, organization_slug, id):
        org = get_object_or_404(Organization, slug=organization_slug)
        tour = get_object_or_404(Tour, organization=org, id=id)

        unpublish_tour(tour)
        return Response(TourSerializer(tour).data, status=status.HTTP_200_OK)


class RebuildTourManifestView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def post(self, request, organization_slug, id):
        org = get_object_or_404(Organization, slug=organization_slug)
        tour = get_object_or_404(Tour, organization=org, id=id)

        manifest = build_tour_manifest(tour)
        return Response(manifest, status=status.HTTP_200_OK)


class OrgSceneListCreateView(generics.ListCreateAPIView):
    serializer_class = Scene360Serializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get_queryset(self):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])
        return Scene360.objects.filter(
            organization=org,
            tour_id=self.kwargs["tour_id"],
        ).prefetch_related("hotspots").order_by("order", "id")

    def perform_create(self, serializer):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])
        tour = get_object_or_404(
            Tour,
            id=self.kwargs["tour_id"],
            organization=org,
        )

        scene = serializer.save(
            organization=org,
            tour=tour,
        )
        build_tour_manifest(tour)
        return scene


class OrgSceneDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = Scene360Serializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    lookup_field = "id"

    def get_queryset(self):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])
        return Scene360.objects.filter(organization=org).prefetch_related("hotspots")

    def perform_update(self, serializer):
        scene = serializer.save()
        build_tour_manifest(scene.tour)

    def perform_destroy(self, instance):
        tour = instance.tour
        instance.delete()
        build_tour_manifest(tour)


class OrgHotspotListCreateView(generics.ListCreateAPIView):
    serializer_class = HotspotSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get_queryset(self):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])
        return Hotspot.objects.filter(
            organization=org,
            scene_id=self.kwargs["scene_id"],
        ).order_by("id")

    def perform_create(self, serializer):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])
        scene = get_object_or_404(
            Scene360,
            id=self.kwargs["scene_id"],
            organization=org,
        )

        hotspot = serializer.save(
            organization=org,
            scene=scene,
        )
        build_tour_manifest(scene.tour)
        return hotspot


class OrgHotspotDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = HotspotSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    lookup_field = "id"

    def get_queryset(self):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])
        return Hotspot.objects.filter(organization=org)

    def perform_update(self, serializer):
        hotspot = serializer.save()
        build_tour_manifest(hotspot.scene.tour)

    def perform_destroy(self, instance):
        tour = instance.scene.tour
        instance.delete()
        build_tour_manifest(tour)


class OrgTourPhotoListCreateView(generics.ListCreateAPIView):
    serializer_class = TourPhotoSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get_queryset(self):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])
        return TourPhoto.objects.filter(
            organization=org,
            tour_id=self.kwargs["tour_id"],
        ).order_by("order", "id")

    def perform_create(self, serializer):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])
        tour = get_object_or_404(
            Tour,
            id=self.kwargs["tour_id"],
            organization=org,
        )

        serializer.save(
            organization=org,
            tour=tour,
        )


class OrgTourPhotoDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TourPhotoSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    lookup_field = "id"

    def get_queryset(self):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])
        return TourPhoto.objects.filter(organization=org)
    
    