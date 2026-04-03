from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from apps.organizations.models import Organization
from apps.organizations.permissions import IsOrganizationMember
from apps.places.models import Place
from .models import Lead
from .serializers import LeadSerializer, PublicLeadCreateSerializer

class PublicLeadCreateView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicLeadCreateSerializer

    def perform_create(self, serializer):
        place = get_object_or_404(Place, id=self.request.data.get("place"), status=Place.Status.PUBLISHED)
        serializer.save(place=place, organization=place.organization)

class OrgLeadListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    serializer_class = LeadSerializer

    def get_queryset(self):
        org = get_object_or_404(Organization, slug=self.kwargs["organization_slug"])
        return Lead.objects.filter(organization=org).select_related("place").order_by("-created_at")
    
    