from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import OrganizationSerializer
from .selectors import get_user_organizations

class MyOrganizationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = get_user_organizations(request.user)
        return Response(OrganizationSerializer(qs, many=True).data)