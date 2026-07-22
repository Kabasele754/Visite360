from django.contrib import admin

from apps.knowledge.models import FAQItem, KnowledgeChunk, KnowledgeDocument, KnowledgeSource, ServiceOffering


@admin.register(KnowledgeSource)
class KnowledgeSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "source_type", "status", "last_synced_at", "is_active")
    list_filter = ("source_type", "status", "is_active")
    search_fields = ("name", "url", "organization__name")


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "language", "indexed_at", "is_active")
    search_fields = ("title", "canonical_url", "clean_content")


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "position", "token_count")
    search_fields = ("content", "document__title")


admin.site.register(FAQItem)
admin.site.register(ServiceOffering)
