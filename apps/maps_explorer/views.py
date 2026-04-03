from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from apps.places.models import Place
from apps.organizations.models import Organization
from apps.organizations.permissions import IsOrganizationMember
from .models import PlaceMapContext
from .serializers import PlaceMapContextSerializer

class PublicPlaceMapContextView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = PlaceMapContextSerializer

    def get_object(self):
        place = get_object_or_404(Place, slug=self.kwargs["slug"], status=Place.Status.PUBLISHED)
        return get_object_or_404(PlaceMapContext, place=place)

class OrgPlaceMapContextUpsertView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    serializer_class = PlaceMapContextSerializer

    def perform_create(self, serializer):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])
        place = get_object_or_404(Place, id=self.request.data.get("place"), organization=org)
        PlaceMapContext.objects.update_or_create(
            place=place,
            defaults={**serializer.validated_data, "organization": org},
        )
        
        
        