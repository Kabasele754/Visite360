from rest_framework import serializers
from .models import Lead

class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            "id", "organization", "place", "full_name", "phone", "email",
            "message", "source", "status", "created_at"
        ]
        read_only_fields = ["status", "created_at", "organization"]

class PublicLeadCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = ["place", "full_name", "phone", "email", "message", "source"]
        
        