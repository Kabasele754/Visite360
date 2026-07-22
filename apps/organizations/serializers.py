from rest_framework import serializers
from .models import Organization, OrganizationMember

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id", "name", "slug", "status", "description", "website_url", "booking_url",
            "public_email", "public_phone", "facebook_url", "instagram_url", "tiktok_url",
            "linkedin_url", "youtube_url", "ai_use_website", "ai_auto_discover_social_links",
            "social_links_verified_at", "created_at",
        ]

class OrganizationMemberSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = OrganizationMember
        fields = ["id", "organization", "user", "user_email", "role", "is_active", "created_at"]