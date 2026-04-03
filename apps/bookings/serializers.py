from rest_framework import serializers
from .models import BookingRequest

class BookingRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingRequest
        fields = "__all__"
        read_only_fields = ["organization", "status", "created_at", "updated_at"]
        
        