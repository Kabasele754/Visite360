from rest_framework import generics
from rest_framework.permissions import AllowAny
from .models import AnalyticsEvent
from .serializers import AnalyticsEventSerializer

class AnalyticsEventCreateView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = AnalyticsEventSerializer
    queryset = AnalyticsEvent.objects.all()
    
    