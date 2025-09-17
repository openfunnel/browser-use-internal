import pytest
from unittest.mock import AsyncMock, patch

from gtm_agent.config import AgentConfig
from gtm_agent.extraction import CompanyExtractor
from gtm_agent.llm.types import ChatMessage, LLMResult
from gtm_agent.orchestrator import AgentContext
from gtm_agent.tools.extraction import CompanyExtractionTool


class StubDom:
    async def query_text_all(self, selector: str, limit=None):
        if selector in {".company", "li"}:
            return [
                "Company A — Platform services",
                "Company B",
                "Privacy Policy",
            ]
        return []


class StubLLM:
    def __init__(self) -> None:
        self.messages = None

    async def complete(self, messages, *, max_tokens, temperature):
        self.messages = messages
        return LLMResult(
            text="[{'name': 'Company A', 'context': 'Platform services'}]".replace("'", '"'),
            raw=None,
        )


class StubVision:
    def __init__(self) -> None:
        self.requests = []

    async def describe(self, payload):
        self.requests.append(payload)
        return LLMResult(
            text="[{'name': 'Vision Co', 'context': 'Screenshot derived'}]".replace("'", '"'),
            raw=None,
        )


class StubDomEmpty:
    async def query_text_all(self, selector: str, limit=None):
        return []


class StubLLMDom:
    def __init__(self) -> None:
        self.messages = None

    async def complete(self, messages, *, max_tokens, temperature):
        self.messages = messages
        return LLMResult(
            text="[{'name': 'Dom LLM Co', 'context': 'Case study heading'}]".replace("'", '"'),
            raw=None,
        )


class StubVisionTextLLM:
    def __init__(self) -> None:
        self.messages = None

    async def complete(self, messages, *, max_tokens, temperature):
        self.messages = messages
        return LLMResult(
            text="[{'name': 'Central'}, {'name': 'Fini'}, {'name': 'NUMI'}, {'name': 'Cekura'}]".replace("'", '"'),
            raw=None,
        )


class StubVisionEnum:
    def __init__(self) -> None:
        self.calls = []

    async def describe(self, payload):
        self.calls.append(payload)
        return LLMResult(
            text=(
                "Based on the case studies shown in the image, here are the customers:\n"
                "1. Central\n2. Fini\n3. NUMI\n4. Cekura\n"
            ),
            raw=None,
        )


@pytest.mark.asyncio
async def test_company_extractor_filters_and_formats():
    extractor = CompanyExtractor(dom=StubDom())
    results = await extractor.extract()

    names = [record.name for record in results]
    assert "Company A" in names
    assert "Privacy Policy" not in names


@pytest.mark.asyncio
async def test_company_extractor_uses_llm_when_available():
    llm = StubLLM()
    extractor = CompanyExtractor(dom=StubDom(), llm=llm)
    results = await extractor.extract(max_results=3)

    assert [record.name for record in results] == ["Company A"]
    assert isinstance(llm.messages[0], ChatMessage)


@pytest.mark.asyncio
async def test_company_extractor_merges_vision_results():
    vision = StubVision()
    extractor = CompanyExtractor(dom=StubDom(), vision_llm=vision)
    results = await extractor.extract(max_results=3, screenshot_bytes=b"img data")

    names = {record.name for record in results}
    assert "Vision Co" in names
    assert vision.requests, "Expected the vision client to be called"


@pytest.mark.asyncio
async def test_company_extraction_tool_captures_screenshot_for_vision():
    class StubPage:
        async def screenshot(self, full_page=True):
            return b"auto-shot"

    context = AgentContext(goal="", url="", config=AgentConfig())
    context.artifacts["page"] = StubPage()

    tool = CompanyExtractionTool(vision_llm=object())

    with patch("gtm_agent.tools.extraction.CompanyExtractor") as mock_extractor_cls:
        mock_instance = mock_extractor_cls.return_value
        mock_instance.extract = AsyncMock(return_value=[])
        mock_instance.debug_events = []

        await tool.execute(context)

        mock_instance.extract.assert_awaited()
        kwargs = mock_instance.extract.await_args.kwargs
        assert kwargs["screenshot_bytes"] == b"auto-shot"
        assert context.artifacts["last_screenshot_bytes"] == b"auto-shot"


@pytest.mark.asyncio
async def test_company_extractor_falls_back_to_dom_llm_when_no_candidates():
    llm = StubLLMDom()
    extractor = CompanyExtractor(dom=StubDomEmpty(), llm=llm)
    dom_excerpt = "<section><h2>Dom LLM Co</h2><p>Success story</p></section>"
    results = await extractor.extract(max_results=5, dom_excerpt=dom_excerpt)

    assert [record.name for record in results] == ["Dom LLM Co"]
    assert llm.messages, "Expected DOM LLM call"


@pytest.mark.asyncio
async def test_company_extractor_vision_fallback_uses_text_llm():
    text_llm = StubVisionTextLLM()
    vision = StubVisionEnum()
    extractor = CompanyExtractor(dom=StubDomEmpty(), llm=text_llm, vision_llm=vision)

    results = await extractor._extract_with_vision(
        b"image-bytes", mime_type="image/png", goal="Find customers", max_results=10
    )

    assert [record.name for record in results] == ["Central", "Fini", "NUMI", "Cekura"]
    assert text_llm.messages is not None, "Expected text LLM to format vision response"
