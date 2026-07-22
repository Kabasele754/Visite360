from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from typing import Any

from django.db import connection
from pgvector.django import CosineDistance

from apps.ai_core.services.router import AIProviderRouter
from apps.knowledge.models import KnowledgeChunk

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SearchHit:
    chunk_id: int
    document_id: str
    title: str
    source_name: str
    content: str
    url: str
    score: float
    metadata: dict[str, Any]


def _lexical_score(query: str, content: str) -> float:
    query_terms = set(re.findall(r"\w+", query.lower()))
    content_terms = set(re.findall(r"\w+", content.lower()))
    if not query_terms:
        return 0.0
    return len(query_terms & content_terms) / len(query_terms)


def semantic_search(*, organization, query: str, limit: int = 8, router: AIProviderRouter | None = None) -> list[SearchHit]:
    queryset = KnowledgeChunk.objects.select_related("document__source").filter(
        document__source__organization=organization,
        document__source__is_active=True,
        document__is_active=True,
    )
    router = router or AIProviderRouter(organization=organization)
    vector = router.embed([query])[0]
    if connection.vendor == "postgresql":
        provider = getattr(router, "last_embedding_provider", "")
        model = getattr(router, "last_embedding_model", "")
        vector_queryset = queryset.exclude(embedding=None)
        if provider and model:
            matching_queryset = vector_queryset.filter(
                metadata__embedding_provider=provider,
                metadata__embedding_model=model,
            )
            if matching_queryset.exists():
                vector_queryset = matching_queryset
            else:
                logger.warning(
                    "No knowledge vectors match embedding space %s/%s; "
                    "using lexical fallback until reindex_knowledge is run.",
                    provider,
                    model,
                )
                vector_queryset = None
        if vector_queryset is not None:
            rows = vector_queryset.annotate(
                distance=CosineDistance("embedding", vector)
            ).order_by("distance")[:limit]
            return [
                SearchHit(
                    chunk_id=row.id,
                    document_id=str(row.document_id),
                    title=row.document.title,
                    source_name=row.document.source.name,
                    content=row.content,
                    url=row.document.canonical_url,
                    score=max(0.0, 1.0 - float(row.distance)),
                    metadata=row.metadata,
                )
                for row in rows
            ]

    candidates = list(queryset[:500])
    ranked = sorted(
        ((chunk, _lexical_score(query, chunk.content)) for chunk in candidates),
        key=lambda item: item[1],
        reverse=True,
    )[:limit]
    return [
        SearchHit(
            chunk_id=chunk.id,
            document_id=str(chunk.document_id),
            title=chunk.document.title,
            source_name=chunk.document.source.name,
            content=chunk.content,
            url=chunk.document.canonical_url,
            score=score,
            metadata=chunk.metadata,
        )
        for chunk, score in ranked
        if score > 0
    ]
