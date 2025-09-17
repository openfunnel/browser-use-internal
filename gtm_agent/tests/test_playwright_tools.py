from pathlib import Path

import pytest

from gtm_agent.playwright_session import PlaywrightSessionManager
from gtm_agent.config import AgentConfig
from gtm_agent.tools.actions import ActionToolbox
from gtm_agent.tools.dom import DomToolbox
from gtm_agent.tools.interaction import ClickSelectorTool
from gtm_agent.tools.observation import ObservePageTool
from gtm_agent.orchestrator import AgentContext


@pytest.mark.asyncio
async def test_dom_toolbox_snapshot_and_query():
    manager = PlaywrightSessionManager()

    async with manager.start() as resources:
        page = resources.page
        file_path = Path(__file__).parent / "sample_page.html"
        await page.goto(file_path.as_uri())

        dom = DomToolbox(page)
        snapshot = await dom.snapshot()
        assert "Company A" in snapshot

        texts = await dom.query_text_all(".company")
        assert "Company A — Platform services" in texts
        assert len(texts) == 2


@pytest.mark.asyncio
async def test_action_toolbox_click_appends_company():
    manager = PlaywrightSessionManager()

    async with manager.start() as resources:
        page = resources.page
        file_path = Path(__file__).parent / "sample_page.html"
        await page.goto(file_path.as_uri())

        actions = ActionToolbox(page)
        dom = DomToolbox(page)

        await actions.click("#load-more")
        await page.wait_for_timeout(200)

        texts = await dom.query_text_all(".company")
        assert "Company C — Automation tools" in texts
        assert len(texts) == 3


@pytest.mark.asyncio
async def test_observe_tool_captures_dom_and_screenshot():
    manager = PlaywrightSessionManager()

    async with manager.start() as resources:
        page = resources.page
        file_path = Path(__file__).parent / "sample_page.html"
        await page.goto(file_path.as_uri())

        context = AgentContext(goal="Test", url="", config=AgentConfig(), artifacts={"page": page})
        tool = ObservePageTool()
        result = await tool.execute(context)

        assert result.success
        assert "Company A" in result.observation["dom_excerpt"]
        assert result.observation.get("screenshot_available") is True
        assert "last_screenshot_bytes" in context.artifacts
        assert result.observation["scroll_height"] >= result.observation["viewport_height"]
        assert result.observation["is_at_bottom"]


@pytest.mark.asyncio
async def test_click_selector_tool_uses_context_page():
    manager = PlaywrightSessionManager()

    async with manager.start() as resources:
        page = resources.page
        file_path = Path(__file__).parent / "sample_page.html"
        await page.goto(file_path.as_uri())

        context = AgentContext(goal="Test", url="", config=AgentConfig(), artifacts={"page": page})
        click_tool = ClickSelectorTool()
        result = await click_tool.execute(context, selector="#load-more", wait_after_ms=100)

        assert result.success
        dom = DomToolbox(page)
        texts = await dom.query_text_all(".company")
        assert len(texts) == 3
