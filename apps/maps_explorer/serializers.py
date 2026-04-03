from rest_framework import serializers

from .models import PlaceMapContext

class PlaceMapContextSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaceMapContext
        fields = [
            "place", "street_view_available", "street_view_lat", "street_view_lng",
            "heading", "pitch", "zoom", "geocode_payload"
        ]
        
