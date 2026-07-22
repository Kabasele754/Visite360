from celery import shared_task
from django.utils import timezone

from apps.knowledge.models import FAQItem, KnowledgeSource, ServiceOffering
from apps.knowledge.services.crawler import crawl_website, discover_social_links
from apps.knowledge.services.indexing import index_document, load_source_file, upsert_document


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def sync_knowledge_source(self, source_id: int):
    source = KnowledgeSource.objects.select_related("organization").get(pk=source_id)
    source.status = KnowledgeSource.Status.CRAWLING
    source.last_error = ""
    source.save(update_fields=("status", "last_error", "updated_at"))
    indexed = 0
    try:
        if source.source_type == KnowledgeSource.SourceType.WEBSITE:
            pages = crawl_website(
                source.url,
                max_pages=source.max_pages,
                same_domain_only=source.crawl_same_domain_only,
            )
            if source.organization.ai_auto_discover_social_links:
                discovered = discover_social_links(pages)
                changed = []
                for field, value in discovered.items():
                    if not getattr(source.organization, field, ""):
                        setattr(source.organization, field, value)
                        changed.append(field)
                if changed:
                    source.organization.social_links_verified_at = timezone.now()
                    changed.append("social_links_verified_at")
                    source.organization.save(update_fields=changed + ["updated_at"])
            for page in pages:
                document = upsert_document(
                    source=source,
                    title=page.title,
                    content=page.text,
                    canonical_url=page.url,
                    metadata={"crawler": "beautifulsoup"},
                )
                indexed += index_document(document)
        elif source.source_type == KnowledgeSource.SourceType.DOCUMENT:
            content = load_source_file(source)
            document = upsert_document(source=source, title=source.name, content=content)
            indexed += index_document(document)
        elif source.source_type == KnowledgeSource.SourceType.FAQ:
            for faq in FAQItem.objects.filter(organization=source.organization, is_active=True):
                content = f"Question: {faq.question}\nAnswer: {faq.answer}"
                document = upsert_document(
                    source=source,
                    title=faq.question,
                    content=content,
                    external_id=f"faq:{faq.pk}",
                    metadata={"category": faq.category, "locale": faq.locale},
                )
                indexed += index_document(document)
        elif source.source_type == KnowledgeSource.SourceType.SERVICE:
            for service in ServiceOffering.objects.filter(organization=source.organization, is_active=True):
                content = "\n".join(filter(None, [
                    service.name,
                    service.short_description,
                    service.description,
                    f"Category: {service.category}" if service.category else "",
                    f"Price from: {service.price_from} {service.currency}" if service.price_from is not None else "",
                ]))
                document = upsert_document(
                    source=source,
                    title=service.name,
                    content=content,
                    canonical_url=service.booking_url,
                    external_id=f"service:{service.pk}",
                    metadata={"service_id": service.pk},
                )
                indexed += index_document(document)
        elif source.source_type == KnowledgeSource.SourceType.PRODUCT:
            from apps.vendors.models import Product
            for product in Product.objects.filter(organization=source.organization, status=Product.Status.ACTIVE):
                content = "\n".join(filter(None, [
                    product.name,
                    product.short_description,
                    product.description,
                    f"Price: {product.price} {product.currency}",
                    f"Specifications: {product.specifications}",
                ]))
                document = upsert_document(
                    source=source,
                    title=product.name,
                    content=content,
                    external_id=f"product:{product.pk}",
                    metadata={"product_id": product.pk, "slug": product.slug},
                )
                indexed += index_document(document)
        source.status = KnowledgeSource.Status.INDEXED
        source.last_synced_at = timezone.now()
        source.save(update_fields=("status", "last_synced_at", "updated_at"))
        return {"source_id": source_id, "chunks_indexed": indexed}
    except Exception as exc:
        source.status = KnowledgeSource.Status.FAILED
        source.last_error = str(exc)[:8000]
        source.save(update_fields=("status", "last_error", "updated_at"))
        raise
