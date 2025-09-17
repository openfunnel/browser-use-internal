import base64

import pytest

from gtm_agent.config import LLMConfig
from gtm_agent.llm.anthropic import AnthropicTextClient, AnthropicVisionClient
from gtm_agent.llm.prompts import PlannerPromptBuilder, ToolDescriptor
from gtm_agent.llm.types import ChatMessage, VisionPrompt


class FakeContent:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.content = [FakeContent(text)]


class FakeMessages:
    def __init__(self) -> None:
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse("ok")


class FakeAnthropic:
    def __init__(self) -> None:
        self.messages = FakeMessages()


@pytest.mark.asyncio
async def test_anthropic_text_client_formats_messages():
    client = AnthropicTextClient(
        config=LLMConfig(text_model="test-model", max_tokens=256, temperature=0.1),
        client=FakeAnthropic(),
    )

    messages = [
        ChatMessage(role="system", content="You are helpful."),
        ChatMessage(role="user", content="Hello"),
    ]

    result = await client.complete(messages, max_tokens=128, temperature=0.5)

    assert result.text == "ok"

    call = client._client.messages.calls[0]
    assert call["system"] == "You are helpful."
    assert call["max_tokens"] == 128
    assert call["temperature"] == 0.5
    assert call["messages"][0]["role"] == "user"
    assert call["messages"][0]["content"][0]["text"] == "Hello"


@pytest.mark.asyncio
async def test_anthropic_vision_client_encodes_images():
    fake_anthropic = FakeAnthropic()
    vision = AnthropicVisionClient(
        config=LLMConfig(vision_model="vision-model", max_tokens=200), client=fake_anthropic
    )

    payload = VisionPrompt(prompt="Describe", image_bytes=b"image-bytes", mime_type="image/png", max_tokens=64)
    result = await vision.describe(payload)

    assert result.text == "ok"

    call = fake_anthropic.messages.calls[0]
    image_block = call["messages"][0]["content"][1]
    assert image_block["source"]["media_type"] == "image/png"
    decoded = base64.b64decode(image_block["source"]["data"])
    assert decoded == b"image-bytes"
    assert call["max_tokens"] == 64


def test_planner_prompt_builder_shapes_messages():
    builder = PlannerPromptBuilder(system_prompt="System guidance")
    messages = builder.build(
        goal="Find companies",
        url="https://example.com",
        notes=["Scrolled", "Clicked load more"],
        observations=[{"companies": 3}],
        tools=[ToolDescriptor(name="dom_snapshot", description="Get DOM")],
    )

    assert messages[0].role == "system"
    assert "Find companies" in messages[1].content
    assert "dom_snapshot" in messages[1].content
    assert "Clicked load more" in messages[1].content
