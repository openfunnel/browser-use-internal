"""Abstract client interfaces for LLM operations."""

from __future__ import annotations

from typing import Protocol, Sequence

from .types import ChatMessage, LLMResult, VisionPrompt


class TextLLMClient(Protocol):
    """Protocol for chat-completion style LLM clients."""

    async def complete(self, messages: Sequence[ChatMessage], *, max_tokens: int, temperature: float) -> LLMResult:
        """Execute a chat completion and return normalized result."""


class VisionLLMClient(Protocol):
    """Protocol for vision-capable multimodal clients."""

    async def describe(self, payload: VisionPrompt) -> LLMResult:
        """Return a textual description for the provided image prompt."""


__all__ = ["TextLLMClient", "VisionLLMClient"]
