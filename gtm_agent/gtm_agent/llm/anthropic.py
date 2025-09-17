"""Anthropic client wrappers for text and vision interactions."""

from __future__ import annotations

import base64
from typing import Optional, Sequence

from anthropic import AsyncAnthropic

from ..config import LLMConfig
from .base import TextLLMClient, VisionLLMClient
from .types import ChatMessage, LLMResult, VisionPrompt


def _format_messages(messages: Sequence[ChatMessage]) -> tuple[str | None, list[dict]]:
    system_chunks: list[str] = []
    chat_messages: list[dict] = []
    for message in messages:
        if message.role == "system":
            system_chunks.append(message.content)
            continue
        chat_messages.append(
            {
                "role": message.role,
                "content": [
                    {
                        "type": "text",
                        "text": message.content,
                    }
                ],
            }
        )
    system_prompt = "\n".join(system_chunks) if system_chunks else None
    return system_prompt, chat_messages


class AnthropicTextClient(TextLLMClient):
    """Thin wrapper translating generic chat messages to Anthropic API calls."""

    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        *,
        client: Optional[AsyncAnthropic] = None,
    ) -> None:
        self.config = config or LLMConfig()
        self._client = client or AsyncAnthropic()

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResult:
        system_prompt, chat_messages = _format_messages(messages)
        response = await self._client.messages.create(
            model=self.config.text_model,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature if temperature is not None else self.config.temperature,
            system=system_prompt,
            messages=chat_messages,
        )

        text_chunks = [chunk.text for chunk in response.content if chunk.type == "text"]
        return LLMResult(text="".join(text_chunks), raw=response)


class AnthropicVisionClient(VisionLLMClient):
    """Vision helper using Anthropic multimodal models."""

    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        *,
        client: Optional[AsyncAnthropic] = None,
    ) -> None:
        self.config = config or LLMConfig()
        self._client = client or AsyncAnthropic()

    async def describe(self, payload: VisionPrompt) -> LLMResult:
        image_b64 = base64.b64encode(payload.image_bytes).decode("ascii")
        response = await self._client.messages.create(
            model=self.config.vision_model or self.config.text_model,
            max_tokens=payload.max_tokens or self.config.max_tokens,
            temperature=self.config.temperature,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": payload.prompt},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": payload.mime_type,
                                "data": image_b64,
                            },
                        },
                    ],
                }
            ],
        )

        text_chunks = [chunk.text for chunk in response.content if chunk.type == "text"]
        return LLMResult(text="".join(text_chunks), raw=response)


__all__ = ["AnthropicTextClient", "AnthropicVisionClient"]
