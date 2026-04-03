from rest_framework import serializers
from .models import Place


class PlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Place
        fields = [
            "id",
            "organization",
            "name",
            "slug",
            "category",
            "description",
            "address_line",
            "city",
            "country",
            "latitude",
            "longitude",
            "cover_image",
            "status",
            "published_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "organization",
            "published_at",
            "created_at",
            "updated_at",
        ]


class PublicPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Place
        fields = [
            "id",
            "name",
            "slug",
            "category",
            "description",
            "address_line",
            "city",
            "country",
            "latitude",
            "longitude",
            "cover_image",
            "published_at",
        ]