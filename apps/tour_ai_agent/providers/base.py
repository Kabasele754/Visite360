from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class AITextResponse:
    text: str
    provider: str
    response_id: str | None = None
    raw: Any = None


class TextProvider(Protocol):
    name: str

    @property
    def enabled(self) -> bool:
        ...

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> AITextResponse:
        ...