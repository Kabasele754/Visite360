from __future__ import annotations

import hashlib
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from apps.ai_core.services.router import AIProviderRouter
from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument, KnowledgeSource
from apps.knowledge.services.chunking import chunk_text, normalize_text


def checksum_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@transaction.atomic
def upsert_document(*, source: KnowledgeSource, title: str, content: str, canonical_url: str = "", external_id: str = "", metadata: dict | None = None) -> KnowledgeDocument:
    clean = normalize_text(content)
    checksum = checksum_text(clean)
    document, created = KnowledgeDocument.objects.get_or_create(
        source=source,
        checksum=checksum,
        defaults={
            "title": title[:500],
            "canonical_url": canonical_url,
            "external_id": external_id,
            "raw_content": content,
            "clean_content": clean,
            "metadata": metadata or {},
        },
    )
    if not created:
        document.title = title[:500]
        document.canonical_url = canonical_url
        document.external_id = external_id
        document.raw_content = content
        document.clean_content = clean
        document.metadata = metadata or document.metadata
        document.is_active = True
        document.save()
    return document


@transaction.atomic
def index_document(document: KnowledgeDocument, *, router: AIProviderRouter | None = None) -> int:
    router = router or AIProviderRouter(organization=document.source.organization)
    chunks = chunk_text(document.clean_content)
    vectors = router.embed([chunk.content for chunk in chunks]) if chunks else []
    embedding_metadata = {
        "embedding_provider": getattr(router, "last_embedding_provider", ""),
        "embedding_model": getattr(router, "last_embedding_model", ""),
        "embedding_dimensions": getattr(router, "last_embedding_dimensions", 0),
    }
    document.chunks.all().delete()
    KnowledgeChunk.objects.bulk_create([
        KnowledgeChunk(
            document=document,
            position=chunk.position,
            content=chunk.content,
            token_count=chunk.token_count,
            embedding=vectors[index] if index < len(vectors) else None,
            metadata=embedding_metadata,
        )
        for index, chunk in enumerate(chunks)
    ])
    document.indexed_at = timezone.now()
    document.save(update_fields=("indexed_at", "updated_at"))
    return len(chunks)


def load_source_file(source: KnowledgeSource) -> str:
    if not source.file:
        return ""
    suffix = Path(source.file.name).suffix.lower()
    source.file.open("rb")
    data = source.file.read()
    source.file.close()
    if suffix in {".txt", ".md", ".csv", ".json", ".html", ".htm"}:
        return data.decode("utf-8", errors="replace")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("Install pypdf to index PDF documents.") from exc
        reader = PdfReader(source.file.path)
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    raise RuntimeError(f"Unsupported knowledge file type: {suffix}")
