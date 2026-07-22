from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.ai_core.services.router import AIProviderRouter
from apps.knowledge.models import KnowledgeDocument
from apps.knowledge.services.indexing import index_document


class Command(BaseCommand):
    help = "Rebuild knowledge embeddings after changing the embedding provider or dimensionality configuration."

    def add_arguments(self, parser):
        parser.add_argument("--organization", type=int)
        parser.add_argument("--source", type=int)
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--fail-fast", action="store_true")

    def handle(self, *args, **options):
        qs = KnowledgeDocument.objects.select_related("source__organization").filter(
            is_active=True,
            source__is_active=True,
        ).order_by("source__organization_id", "source_id", "id")
        if options["organization"]:
            qs = qs.filter(source__organization_id=options["organization"])
        if options["source"]:
            qs = qs.filter(source_id=options["source"])
        if options["limit"]:
            qs = qs[: options["limit"]]

        documents = list(qs)
        if not documents:
            self.stdout.write(self.style.WARNING("No knowledge documents matched."))
            return

        routers = {}
        success = 0
        errors = 0
        for index, document in enumerate(documents, 1):
            organization = document.source.organization
            router = routers.setdefault(
                organization.pk,
                AIProviderRouter(organization=organization),
            )
            try:
                count = index_document(document, router=router)
                success += 1
                self.stdout.write(self.style.SUCCESS(
                    f"[{index}/{len(documents)}] document={document.pk} chunks={count} "
                    f"organization={organization.pk}"
                ))
            except Exception as exc:
                errors += 1
                self.stdout.write(self.style.ERROR(
                    f"[{index}/{len(documents)}] document={document.pk} failed: {exc}"
                ))
                if options["fail_fast"]:
                    raise

        self.stdout.write(json.dumps({
            "documents": len(documents),
            "succeeded": success,
            "failed": errors,
        }))
