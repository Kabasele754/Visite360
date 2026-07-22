from rest_framework import serializers
from .models import Tour, Scene360, Hotspot, TourPhoto


class HotspotSerializer(serializers.ModelSerializer):
    ad_image_url = serializers.SerializerMethodField()
    media_file_url = serializers.SerializerMethodField()
    poster_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Hotspot
        fields = [
            "id",
            "organization",
            "scene",
            "hotspot_id",
            "type",
            "label",
            "yaw",
            "pitch",
            "target_scene",
            "tooltip_text",
            "title",
            "description",
            "selected_icon",
            "ad_image",
            "ad_image_url",
            "media_file",
            "media_file_url",
            "poster_image",
            "poster_image_url",
            "payload",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "organization",
            "ad_image_url",
            "media_file_url",
            "poster_image_url",
            "created_at",
            "updated_at",
        ]

    def get_ad_image_url(self, obj):
        return obj.ad_image.url if obj.ad_image else None

    def get_media_file_url(self, obj):
        return obj.media_file.url if obj.media_file else None

    def get_poster_image_url(self, obj):
        return obj.poster_image.url if obj.poster_image else None


class Scene360Serializer(serializers.ModelSerializer):
    image_360_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    hotspots = HotspotSerializer(many=True, read_only=True)

    class Meta:
        model = Scene360
        fields = [
            "id",
            "organization",
            "tour",
            "scene_id",
            "title",
            "image_360",
            "image_360_url",
            "thumbnail_image",
            "thumbnail_url",
            "order",
            "yaw_default",
            "pitch_default",
            "hfov_default",
            "hotspots",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "organization",
            "image_360_url",
            "thumbnail_url",
            "hotspots",
            "created_at",
            "updated_at",
        ]

    def get_image_360_url(self, obj):
        return obj.image_360.url if obj.image_360 else None

    def get_thumbnail_url(self, obj):
        return obj.thumbnail_image.url if obj.thumbnail_image else None


class TourPhotoSerializer(serializers.ModelSerializer):
    organization = serializers.IntegerField(source="tour.organization_id", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = TourPhoto
        fields = [
            "id",
            "organization",
            "tour",
            "image",
            "image_url",
            "caption",
            "order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "organization",
            "image_url",
            "created_at",
            "updated_at",
        ]

    def get_image_url(self, obj):
        return obj.image.url if obj.image else None


class TourSerializer(serializers.ModelSerializer):
    thumbnail_image_url = serializers.SerializerMethodField()
    scenes = Scene360Serializer(many=True, read_only=True)
    photos = TourPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Tour
        fields = [
            "id",
            "organization",
            "place",
            "title",
            "slug",
            "description",
            "thumbnail_image",
            "thumbnail_image_url",
            "video_tour",
            "virtual_tour_url",
            "version",
            "status",
            "manifest",
            "tour_date",
            "duration",
            "price",
            "is_featured",
            "max_participants",
            "rating",
            "view_count",
            "guide_name",
            "contact_email",
            "location",
            "lat",
            "lng",
            "radius",
            "chambres",
            "balcon",
            "floor_number",
            "parking",
            "ascenseur",
            "scenes",
            "photos",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "organization",
            "manifest",
            "view_count",
            "thumbnail_image_url",
            "scenes",
            "photos",
            "created_at",
            "updated_at",
        ]

    def get_thumbnail_image_url(self, obj):
        return obj.thumbnail_image.url if obj.thumbnail_image else None


class PublicTourSerializer(serializers.ModelSerializer):
    thumbnail_image_url = serializers.SerializerMethodField()
    scenes = Scene360Serializer(many=True, read_only=True)
    photos = TourPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Tour
        fields = [
            "id",
            "place",
            "title",
            "slug",
            "description",
            "thumbnail_image_url",
            "virtual_tour_url",
            "version",
            "status",
            "manifest",
            "tour_date",
            "duration",
            "price",
            "is_featured",
            "max_participants",
            "rating",
            "view_count",
            "guide_name",
            "contact_email",
            "location",
            "lat",
            "lng",
            "radius",
            "chambres",
            "balcon",
            "floor_number",
            "parking",
            "ascenseur",
            "scenes",
            "photos",
            "created_at",
        ]

    def get_thumbnail_image_url(self, obj):
        return obj.thumbnail_image.url if obj.thumbnail_image else None
    
    