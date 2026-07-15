from django.contrib import admin

from .models import (
    StreetViewConnection,
    StreetViewGoogleAccount,
    StreetViewHotspot,
    StreetViewPublishJob,
    StreetViewScene,
    StreetViewTour,
    StreetViewSourcePublication,
    StreetViewSourceSceneState,
    StreetViewSourcePublishJob,
)


class StreetViewSceneInline(admin.TabularInline):
    model = StreetViewScene
    extra = 0
    fields = (
        "order",
        "title",
        "image",
        "latitude",
        "longitude",
        "heading",
        "publish_status",
        "google_photo_id",
    )
    readonly_fields = ("publish_status", "google_photo_id")


class StreetViewConnectionInline(admin.TabularInline):
    model = StreetViewConnection
    extra = 0
    fk_name = "tour"
    fields = ("from_scene", "to_scene", "yaw", "pitch", "label", "order")


@admin.register(StreetViewTour)
class StreetViewTourAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "status", "created_at", "published_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "description", "owner__username", "owner__email")
    readonly_fields = ("public_id", "created_at", "updated_at", "published_at")
    inlines = [StreetViewSceneInline, StreetViewConnectionInline]


@admin.register(StreetViewScene)
class StreetViewSceneAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "tour",
        "has_gps",
        "image_width",
        "image_height",
        "xmp_detected",
        "publish_status",
        "google_photo_id",
    )
    list_filter = ("publish_status", "xmp_detected", "created_at")
    search_fields = ("title", "tour__title", "google_photo_id")
    readonly_fields = ("created_at", "updated_at", "exif_data")


@admin.register(StreetViewConnection)
class StreetViewConnectionAdmin(admin.ModelAdmin):
    list_display = ("tour", "from_scene", "to_scene", "yaw", "pitch", "created_at")
    search_fields = ("tour__title", "from_scene__title", "to_scene__title")


@admin.register(StreetViewHotspot)
class StreetViewHotspotAdmin(admin.ModelAdmin):
    list_display = ("title", "scene", "type", "target_scene", "url", "yaw", "pitch")
    list_filter = ("type", "created_at")
    search_fields = ("title", "description", "scene__title", "url")


@admin.register(StreetViewGoogleAccount)
class StreetViewGoogleAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "google_email", "is_connected", "token_expiry", "updated_at")
    search_fields = ("user__username", "user__email", "google_email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(StreetViewPublishJob)
class StreetViewPublishJobAdmin(admin.ModelAdmin):
    list_display = ("public_id", "tour", "user", "status", "published_scenes", "failed_scenes", "created_at", "finished_at")
    list_filter = ("status", "created_at")
    search_fields = ("tour__title", "user__username", "user__email")
    readonly_fields = ("public_id", "created_at", "updated_at", "finished_at", "log")



class StreetViewSourceSceneStateInline(admin.TabularInline):
    model = StreetViewSourceSceneState
    extra = 0
    fields = (
        "source_scene",
        "latitude",
        "longitude",
        "heading",
        "pitch",
        "publish_status",
        "google_photo_id",
    )
    readonly_fields = ("google_photo_id", "publish_status")


@admin.register(StreetViewSourcePublication)
class StreetViewSourcePublicationAdmin(admin.ModelAdmin):
    list_display = ("source_tour", "owner", "status", "published_at", "updated_at")
    list_filter = ("status", "source_tour__organization", "source_tour__place", "created_at")
    search_fields = ("source_tour__title", "source_tour__place__name", "source_tour__organization__name", "owner__email")
    readonly_fields = ("public_id", "created_at", "updated_at", "published_at")
    inlines = [StreetViewSourceSceneStateInline]


@admin.register(StreetViewSourceSceneState)
class StreetViewSourceSceneStateAdmin(admin.ModelAdmin):
    list_display = ("source_scene", "publication", "publish_status", "google_photo_id", "updated_at")
    list_filter = ("publish_status", "publication__source_tour__organization", "publication__source_tour__place")
    search_fields = ("source_scene__title", "publication__source_tour__title", "google_photo_id")
    readonly_fields = ("created_at", "updated_at")


@admin.register(StreetViewSourcePublishJob)
class StreetViewSourcePublishJobAdmin(admin.ModelAdmin):
    list_display = ("public_id", "publication", "user", "status", "published_scenes", "failed_scenes", "created_at", "finished_at")
    list_filter = ("status", "created_at")
    search_fields = ("publication__source_tour__title", "user__username", "user__email")
    readonly_fields = ("public_id", "created_at", "updated_at", "finished_at", "log")


try:
    from .models import StreetViewQualityReport, StreetViewHistoryEvent, StreetViewAnalyticsEvent

    @admin.register(StreetViewQualityReport)
    class StreetViewQualityReportAdmin(admin.ModelAdmin):
        list_display = ("public_id", "publication", "user", "status", "score", "blockers", "warnings", "created_at")
        list_filter = ("status", "created_at")
        search_fields = ("publication__source_tour__title", "user__username", "user__email")
        readonly_fields = ("public_id", "created_at", "report")

    @admin.register(StreetViewHistoryEvent)
    class StreetViewHistoryEventAdmin(admin.ModelAdmin):
        list_display = ("publication", "action", "source_scene", "user", "created_at")
        list_filter = ("action", "created_at")
        search_fields = ("publication__source_tour__title", "message", "source_scene__title", "user__username", "user__email")
        readonly_fields = ("created_at", "metadata")

    @admin.register(StreetViewAnalyticsEvent)
    class StreetViewAnalyticsEventAdmin(admin.ModelAdmin):
        list_display = ("publication", "event_type", "source_scene", "user", "created_at")
        list_filter = ("event_type", "created_at")
        search_fields = ("publication__source_tour__title", "source_scene__title", "user__username", "user__email")
        readonly_fields = ("created_at", "metadata")
except admin.sites.AlreadyRegistered:
    pass
