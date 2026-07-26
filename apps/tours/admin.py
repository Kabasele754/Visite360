from django.contrib import admin

from apps.tours.models import (
    Hotspot,
    Scene360,
    SceneLinkProposal,
    SceneObjectCandidate,
    SceneVisualQuality,
    Tour,
    TourArchitectureRun,
)


@admin.register(Scene360)
class Scene360Admin(admin.ModelAdmin):
    list_display = ("id", "title", "tour", "order", "ai_analysis_status", "ai_analyzed_at")
    list_filter = ("ai_analysis_status", "tour__organization")
    search_fields = ("title", "tour__title", "tour__organization__name")


@admin.register(Tour)
class TourAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "organization", "status", "created_at")
    list_filter = ("status", "organization")
    search_fields = ("title", "organization__name")


@admin.register(Hotspot)
class HotspotAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "scene", "type", "target_scene", "is_ai_generated")
    list_filter = ("type", "is_ai_generated", "organization")
    search_fields = ("label", "title", "scene__title", "target_scene__title")


@admin.register(SceneVisualQuality)
class SceneVisualQualityAdmin(admin.ModelAdmin):
    list_display = ("scene", "status", "overall_score", "requires_reupload", "analyzed_at")
    list_filter = ("status", "requires_reupload")
    search_fields = ("scene__title", "scene__tour__title")
    readonly_fields = ("metrics", "issues", "recommendations")


@admin.register(SceneObjectCandidate)
class SceneObjectCandidateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "scene",
        "kind",
        "confidence",
        "clarity_score",
        "is_navigation_anchor",
        "client_ready",
        "review_status",
    )
    list_filter = ("kind", "review_status", "is_navigation_anchor", "client_ready")
    search_fields = ("title", "label", "scene__title", "scene__tour__title")
    readonly_fields = ("fingerprint", "bbox", "issues", "recommendations", "source_providers", "payload")


@admin.register(TourArchitectureRun)
class TourArchitectureRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tour",
        "status",
        "stage",
        "provider",
        "model_name",
        "proposal_count",
        "applied_count",
        "created_at",
    )
    list_filter = ("status", "provider", "organization")
    search_fields = ("tour__title", "organization__name", "id")
    readonly_fields = ("summary", "error_code", "started_at", "finished_at")


@admin.register(SceneLinkProposal)
class SceneLinkProposalAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "from_scene",
        "to_scene",
        "confidence",
        "source",
        "status",
        "is_bidirectional",
        "manual_adjusted",
    )
    list_filter = ("source", "status", "is_bidirectional", "manual_adjusted", "tour")
    search_fields = ("from_scene__title", "to_scene__title", "tour__title", "rationale")
    readonly_fields = ("evidence", "applied_from_hotspot", "applied_reverse_hotspot")
