from __future__ import annotations

from django.conf import settings

from apps.knowledge.services.search import semantic_search


def build_chat_context(conversation, query: str) -> tuple[str, list[dict]]:
    hits = semantic_search(organization=conversation.organization, query=query, limit=8)
    citations = []
    blocks = []
    total = 0
    for index, hit in enumerate(hits, start=1):
        citation_id = f"K{index}"
        citations.append({
            "id": citation_id,
            "chunk_id": hit.chunk_id,
            "document_id": hit.document_id,
            "title": hit.title,
            "source": hit.source_name,
            "url": hit.url,
            "score": hit.score,
        })
        block = f"[{citation_id}] {hit.title}\n{hit.content}"
        if total + len(block) > settings.AI_MAX_CONTEXT_CHARS:
            break
        blocks.append(block)
        total += len(block)

    if conversation.scene_id:
        scene = conversation.scene
        scene_block = f"Current 360 scene: {scene.title}\nVerified scene AI analysis: {scene.ai_analysis}"
        blocks.append(scene_block[:4000])
    return "\n\n".join(blocks), citations
