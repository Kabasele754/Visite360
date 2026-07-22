from __future__ import annotations

import re
from dataclasses import dataclass

from django.conf import settings


@dataclass(slots=True)
class TextChunk:
    position: int
    content: str
    token_count: int


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, *, size: int | None = None, overlap: int | None = None) -> list[TextChunk]:
    size = size or settings.KNOWLEDGE_CHUNK_SIZE
    overlap = overlap if overlap is not None else settings.KNOWLEDGE_CHUNK_OVERLAP
    normalized = normalize_text(text)
    if not normalized:
        return []
    chunks: list[TextChunk] = []
    start = 0
    position = 0
    while start < len(normalized):
        end = min(len(normalized), start + size)
        if end < len(normalized):
            paragraph = normalized.rfind("\n", start + size // 2, end)
            sentence = normalized.rfind(". ", start + size // 2, end)
            boundary = max(paragraph, sentence)
            if boundary > start:
                end = boundary + 1
        content = normalized[start:end].strip()
        if content:
            chunks.append(TextChunk(position=position, content=content, token_count=max(1, len(content) // 4)))
            position += 1
        if end >= len(normalized):
            break
        start = max(start + 1, end - overlap)
    return chunks
