from rest_framework import serializers

from apps.organizations.models import Organization
from apps.places.models import Place
from apps.tours.models import Hotspot, Scene360, Tour, TourPhoto


def absolute_url(request, value):
    """Return a public absolute URL for ImageField/FileField/URLField/string values."""
    if not value:
        return ""

    try:
        raw = value.url
    except Exception:
        raw = str(value or "")

    if not raw:
        return ""

    if raw.startswith("http://") or raw.startswith("https://"):
        return raw

    return request.build_absolute_uri(raw) if request else raw


class OrganizationPublicSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "logo_url"]

    def get_logo_url(self, obj):
        return absolute_url(self.context.get("request"), obj.logo)


class PlacePublicSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = Place
        fields = [
            "id",
            "name",
            "slug",
            "category",
            "category_label",
            "description",
            "address_line",
            "city",
            "country",
            "latitude",
            "longitude",
            "cover_image",
        ]


class HotspotTargetSceneSerializer(serializers.ModelSerializer):
    image_360_preview_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Scene360
        fields = [
            "id",
            "scene_id",
            "title",
            "order",
            "image_360_preview_url",
            "thumbnail_url",
        ]

    def get_image_360_preview_url(self, obj):
        return absolute_url(self.context.get("request"), obj.image_360_preview)

    def get_thumbnail_url(self, obj):
        return absolute_url(self.context.get("request"), obj.thumbnail_image)


class HotspotPublicSerializer(serializers.ModelSerializer):
    target_scene_id = serializers.CharField(source="target_scene.scene_id", read_only=True)
    target_scene_pk = serializers.IntegerField(source="target_scene.id", read_only=True)
    target_scene_title = serializers.CharField(source="target_scene.title", read_only=True)
    target_scene = serializers.SerializerMethodField()
    ad_image_url = serializers.SerializerMethodField()
    action_url = serializers.SerializerMethodField()
    action_label = serializers.SerializerMethodField()
    icon_key = serializers.SerializerMethodField()

    class Meta:
        model = Hotspot
        fields = [
            "id",
            "hotspot_id",
            "type",
            "label",
            "yaw",
            "pitch",
            "target_scene_id",
            "target_scene_pk",
            "target_scene_title",
            "target_scene",
            "tooltip_text",
            "title",
            "description",
            "selected_icon",
            "icon_key",
            "ad_image_url",
            "payload",
            "action_url",
            "action_label",
            "is_ai_generated",
        ]

    def get_target_scene(self, obj):
        if not obj.target_scene_id:
            return None
        return HotspotTargetSceneSerializer(obj.target_scene, context=self.context).data

    def get_ad_image_url(self, obj):
        return absolute_url(self.context.get("request"), obj.ad_image)

    def get_action_url(self, obj):
        payload = obj.payload or {}
        for key in (
            "url",
            "href",
            "link",
            "cta_url",
            "action_url",
            "product_url",
            "website",
            "whatsapp_url",
            "phone_url",
        ):
            value = payload.get(key)
            if value:
                return str(value)
        return ""

    def get_action_label(self, obj):
        payload = obj.payload or {}
        return str(
            payload.get("action_label")
            or payload.get("button_text")
            or payload.get("cta_label")
            or payload.get("label")
            or "Open"
        )

    def get_icon_key(self, obj):
        if obj.selected_icon:
            return obj.selected_icon
        return {
            Hotspot.Type.NAVIGATE: "navigate",
            Hotspot.Type.INFO: "info",
            Hotspot.Type.CTA: "cta",
            Hotspot.Type.PRODUCT: "product",
            Hotspot.Type.CUSTOM: "custom",
        }.get(obj.type, "info")


class ScenePublicSerializer(serializers.ModelSerializer):
    image_360_url = serializers.SerializerMethodField()
    image_360_mobile_url = serializers.SerializerMethodField()
    image_360_preview_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    hotspots = serializers.SerializerMethodField()
    hotspot_count = serializers.SerializerMethodField()
    has_panorama = serializers.SerializerMethodField()

    class Meta:
        model = Scene360
        fields = [
            "id",
            "scene_id",
            "title",
            "order",
            "yaw_default",
            "pitch_default",
            "hfov_default",
            "image_360_url",
            "image_360_mobile_url",
            "image_360_preview_url",
            "thumbnail_url",
            "has_panorama",
            "hotspot_count",
            "hotspots",
        ]

    def get_image_360_url(self, obj):
        return absolute_url(self.context.get("request"), obj.image_360)

    def get_image_360_mobile_url(self, obj):
        return absolute_url(self.context.get("request"), obj.image_360_mobile)

    def get_image_360_preview_url(self, obj):
        return absolute_url(self.context.get("request"), obj.image_360_preview)

    def get_thumbnail_url(self, obj):
        return absolute_url(self.context.get("request"), obj.thumbnail_image)

    def get_hotspots(self, obj):
        qs = obj.hotspots.select_related("target_scene").order_by("id")
        return HotspotPublicSerializer(qs, many=True, context=self.context).data

    def get_hotspot_count(self, obj):
        try:
            return obj.hotspots.count()
        except Exception:
            return 0

    def get_has_panorama(self, obj):
        return bool(obj.image_360 or obj.image_360_mobile)


class TourPhotoPublicSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = TourPhoto
        fields = ["id", "caption", "order", "image_url"]

    def get_image_url(self, obj):
        return absolute_url(self.context.get("request"), obj.image)


class TourCardSerializer(serializers.ModelSerializer):
    organization = OrganizationPublicSerializer(read_only=True)
    place = PlacePublicSerializer(read_only=True)
    category = serializers.CharField(source="place.category", read_only=True)
    category_label = serializers.CharField(source="place.get_category_display", read_only=True)
    city = serializers.CharField(source="place.city", read_only=True)
    country = serializers.CharField(source="place.country", read_only=True)
    scene_count = serializers.IntegerField(read_only=True)
    unique_view_count = serializers.IntegerField(read_only=True)
    share_count = serializers.IntegerField(read_only=True)
    thumbnail_source_url = serializers.SerializerMethodField()
    thumbnail_image_url = serializers.SerializerMethodField()
    thumbnail_image_mobile_url = serializers.SerializerMethodField()
    organization_logo_url = serializers.SerializerMethodField()
    place_cover_image_url = serializers.SerializerMethodField()
    tour_card_image_url = serializers.SerializerMethodField()
    tour_card_image_mobile_url = serializers.SerializerMethodField()
    tour_card_image_high_url = serializers.SerializerMethodField()
    first_scene_image_360_url = serializers.SerializerMethodField()
    first_scene_image_360_mobile_url = serializers.SerializerMethodField()
    first_scene_preview_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()
    detail_url = serializers.SerializerMethodField()
    scenes_url = serializers.SerializerMethodField()
    engagement_url = serializers.SerializerMethodField()

    class Meta:
        model = Tour
        fields = [
            "id",
            "slug",
            "title",
            "description",
            "status",
            "is_featured",
            "rating",
            "price",
            "location",
            "lat",
            "lng",
            "radius",
            "view_count",
            "scene_count",
            "unique_view_count",
            "share_count",
            "organization",
            "place",
            "category",
            "category_label",
            "city",
            "country",
            "thumbnail_source_url",
            "thumbnail_image_url",
            "thumbnail_image_mobile_url",
            "organization_logo_url",
            "place_cover_image_url",
            "tour_card_image_url",
            "tour_card_image_mobile_url",
            "tour_card_image_high_url",
            "first_scene_image_360_url",
            "first_scene_image_360_mobile_url",
            "first_scene_preview_url",
            "preview_url",
            "detail_url",
            "scenes_url",
            "engagement_url",
            "created_at",
            "updated_at",
        ]

    def _first_public_scene(self, obj):
        return (
            obj.scenes.filter(status=Scene360.Status.PUBLISHED, is_public=True)
            .order_by("order", "id")
            .first()
        )

    def get_thumbnail_source_url(self, obj):
        return absolute_url(self.context.get("request"), obj.thumbnail_source)

    def get_thumbnail_image_url(self, obj):
        return absolute_url(self.context.get("request"), obj.thumbnail_image)

    def get_thumbnail_image_mobile_url(self, obj):
        return absolute_url(self.context.get("request"), obj.thumbnail_image_mobile)

    def get_organization_logo_url(self, obj):
        return absolute_url(self.context.get("request"), obj.organization.logo if obj.organization_id else "")

    def get_place_cover_image_url(self, obj):
        return absolute_url(self.context.get("request"), obj.place.cover_image if obj.place_id else "")

    def get_tour_card_image_url(self, obj):
        request = self.context.get("request")
        scene = self._first_public_scene(obj)
        return (
            absolute_url(request, obj.thumbnail_image)
            or absolute_url(request, scene.thumbnail_image if scene else None)
            or absolute_url(request, scene.image_360_preview if scene else None)
            or absolute_url(request, obj.place.cover_image if obj.place_id else "")
        )

    def get_tour_card_image_mobile_url(self, obj):
        request = self.context.get("request")
        scene = self._first_public_scene(obj)
        return (
            absolute_url(request, obj.thumbnail_image_mobile)
            or absolute_url(request, obj.thumbnail_image)
            or absolute_url(request, scene.thumbnail_image if scene else None)
            or absolute_url(request, scene.image_360_preview if scene else None)
            or absolute_url(request, obj.place.cover_image if obj.place_id else "")
        )

    def get_tour_card_image_high_url(self, obj):
        return self.get_thumbnail_source_url(obj) or self.get_tour_card_image_url(obj)

    def get_first_scene_image_360_url(self, obj):
        scene = self._first_public_scene(obj)
        return absolute_url(self.context.get("request"), scene.image_360 if scene else None)

    def get_first_scene_image_360_mobile_url(self, obj):
        scene = self._first_public_scene(obj)
        return absolute_url(self.context.get("request"), scene.image_360_mobile if scene else None)

    def get_first_scene_preview_url(self, obj):
        scene = self._first_public_scene(obj)
        return absolute_url(self.context.get("request"), scene.image_360_preview if scene else None)

    def get_preview_url(self, obj):
        request = self.context.get("request")
        path = f"/preview/{obj.organization.slug}/{obj.id}/"
        return request.build_absolute_uri(path) if request else path

    def get_detail_url(self, obj):
        request = self.context.get("request")
        path = f"/apis/public/tours/{obj.organization.slug}/{obj.id}/"
        return request.build_absolute_uri(path) if request else path

    def get_scenes_url(self, obj):
        request = self.context.get("request")
        path = f"/apis/public/tours/{obj.organization.slug}/{obj.id}/scenes/"
        return request.build_absolute_uri(path) if request else path

    def get_engagement_url(self, obj):
        request = self.context.get("request")
        path = f"/apis/public/tours/{obj.organization.slug}/{obj.id}/engagement/"
        return request.build_absolute_uri(path) if request else path


class TourDetailSerializer(TourCardSerializer):
    scenes = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()

    class Meta(TourCardSerializer.Meta):
        fields = TourCardSerializer.Meta.fields + [
            "scenes",
            "photos",
            "manifest",
            "virtual_tour_url",
        ]

    def get_scenes(self, obj):
        qs = (
            obj.scenes.filter(status=Scene360.Status.PUBLISHED, is_public=True)
            .prefetch_related("hotspots")
            .order_by("order", "id")
        )
        return ScenePublicSerializer(qs, many=True, context=self.context).data

    def get_photos(self, obj):
        return TourPhotoPublicSerializer(
            obj.photos.all().order_by("order", "id"),
            many=True,
            context=self.context,
        ).data
