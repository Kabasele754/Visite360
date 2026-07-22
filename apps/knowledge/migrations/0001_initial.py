import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import pgvector.django.vector


def enable_vector_before_models(apps, schema_editor):
    """Enable pgvector before any VectorField table is created.

    SQLite is kept compatible for local development. On PostgreSQL the
    database user created by the official image owns the application database
    and can install the bundled extension.
    """
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("CREATE EXTENSION IF NOT EXISTS vector")


class Migration(migrations.Migration):
    initial = True
    dependencies = [("organizations", "0003_organization_logo")]
    operations = [
        migrations.RunPython(enable_vector_before_models, migrations.RunPython.noop),
        migrations.CreateModel(
            name="KnowledgeSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("source_type", models.CharField(choices=[("website", "Website"), ("document", "Document"), ("faq", "FAQ"), ("product", "Product catalogue"), ("service", "Service catalogue"), ("manual", "Manual content")], max_length=24)),
                ("url", models.URLField(blank=True)),
                ("file", models.FileField(blank=True, null=True, upload_to="knowledge/sources/%Y/%m/")),
                ("status", models.CharField(choices=[("draft", "Draft"), ("ready", "Ready"), ("crawling", "Crawling"), ("indexed", "Indexed"), ("failed", "Failed"), ("disabled", "Disabled")], db_index=True, default="draft", max_length=24)),
                ("crawl_same_domain_only", models.BooleanField(default=True)),
                ("max_pages", models.PositiveSmallIntegerField(default=25)),
                ("schedule", models.CharField(blank=True, help_text="Optional cron or human-readable schedule.", max_length=80)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="knowledge_sources", to="organizations.organization")),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="FAQItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("question", models.CharField(max_length=500)),
                ("answer", models.TextField()),
                ("category", models.CharField(blank=True, max_length=120)),
                ("locale", models.CharField(default="en", max_length=16)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="faq_items", to="organizations.organization")),
            ],
            options={"ordering": ("order", "question")},
        ),
        migrations.CreateModel(
            name="ServiceOffering",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=280)),
                ("short_description", models.CharField(blank=True, max_length=320)),
                ("description", models.TextField(blank=True)),
                ("category", models.CharField(blank=True, max_length=120)),
                ("price_from", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("currency", models.CharField(default="USD", max_length=8)),
                ("duration_minutes", models.PositiveIntegerField(blank=True, null=True)),
                ("booking_url", models.URLField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="service_offerings", to="organizations.organization")),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="KnowledgeDocument",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=500)),
                ("canonical_url", models.URLField(blank=True)),
                ("external_id", models.CharField(blank=True, max_length=255)),
                ("language", models.CharField(default="en", max_length=16)),
                ("raw_content", models.TextField(blank=True)),
                ("clean_content", models.TextField()),
                ("checksum", models.CharField(db_index=True, max_length=64)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("indexed_at", models.DateTimeField(blank=True, null=True)),
                ("source", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="documents", to="knowledge.knowledgesource")),
            ],
            options={"ordering": ("title",)},
        ),
        migrations.CreateModel(
            name="KnowledgeChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("content", models.TextField()),
                ("token_count", models.PositiveIntegerField(default=0)),
                ("embedding", pgvector.django.vector.VectorField(blank=True, dimensions=1536, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chunks", to="knowledge.knowledgedocument")),
            ],
            options={"ordering": ("document", "position")},
        ),
        migrations.AddConstraint(model_name="knowledgesource", constraint=models.UniqueConstraint(fields=("organization", "name"), name="unique_knowledge_source_name")),
        migrations.AddConstraint(model_name="knowledgedocument", constraint=models.UniqueConstraint(fields=("source", "checksum"), name="unique_knowledge_document_checksum")),
        migrations.AddConstraint(model_name="knowledgechunk", constraint=models.UniqueConstraint(fields=("document", "position"), name="unique_knowledge_chunk_position")),
        migrations.AddConstraint(model_name="serviceoffering", constraint=models.UniqueConstraint(fields=("organization", "slug"), name="unique_service_slug_per_org")),
        migrations.AddIndex(model_name="knowledgedocument", index=models.Index(fields=["source", "external_id"], name="knowledge_k_source__f52921_idx")),
        migrations.AddIndex(model_name="knowledgechunk", index=models.Index(fields=["document", "position"], name="knowledge_k_documen_e8de0a_idx")),
    ]
