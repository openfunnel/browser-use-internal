import pytest

from gtm_agent.extraction import CompanyExtractor
from gtm_agent.llm.types import ChatMessage, LLMResult


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
