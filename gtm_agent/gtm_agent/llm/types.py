"""Shared type definitions for LLM interactions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional


Role = Literal["system", "user", "assistant"]


@dataclass
class ChatMessage:
    role: Role
    content: str


@dataclass
class LLMResult:
    """Normalized LLM response payload."""

    text: str
    raw: Any | None = None


@dataclass
class VisionPrompt:
    prompt: str
    image_bytes: bytes
    mime_type: str = "image/png"
    max_tokens: Optional[int] = None


__all__ = ["ChatMessage", "LLMResult", "VisionPrompt", "Role"]
