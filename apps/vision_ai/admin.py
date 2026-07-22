from django.contrib import admin

from apps.vision_ai.models import OCRTextBlock, VisionAnalysis, VisionDetection, VisionFrame, VisionInsight


@admin.register(VisionAnalysis)
class VisionAnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "scene", "status", "scene_type", "confidence", "created_at")
    list_filter = ("status", "scene_type")
    search_fields = ("summary", "extracted_text", "organization__name", "scene__title")


admin.site.register(VisionFrame)
admin.site.register(VisionDetection)
admin.site.register(OCRTextBlock)

admin.site.register(VisionInsight)
