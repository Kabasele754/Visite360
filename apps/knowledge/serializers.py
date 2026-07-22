from rest_framework import serializers

from apps.knowledge.models import FAQItem, KnowledgeDocument, KnowledgeSource, ServiceOffering


class KnowledgeSourceSerializer(serializers.ModelSerializer):
    documents_count = serializers.IntegerField(source="documents.count", read_only=True)

    class Meta:
        model = KnowledgeSource
        fields = "__all__"
        read_only_fields = ("status", "last_synced_at", "last_error")


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    chunks_count = serializers.IntegerField(source="chunks.count", read_only=True)

    class Meta:
        model = KnowledgeDocument
        fields = (
            "id", "source", "title", "canonical_url", "external_id", "language",
            "checksum", "metadata", "is_active", "indexed_at", "chunks_count", "created_at", "updated_at",
        )


class FAQItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQItem
        fields = "__all__"


class ServiceOfferingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceOffering
        fields = "__all__"
