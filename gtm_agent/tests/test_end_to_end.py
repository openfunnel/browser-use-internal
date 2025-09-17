from pathlib import Path

import pytest

from gtm_agent.config import AgentConfig
from gtm_agent.orchestrator import AgentOrchestrator, ToolAction
from gtm_agent.playwright_session import PlaywrightSessionManager
from gtm_agent.tools.extraction import CompanyExtractionTool


class SingleStepPlanner:
    def __init__(self) -> None:
        self.called = False

    async def select_action(self, context):
        if not self.called:
            self.called = True
            return ToolAction(
                tool_name="company_extract",
                params={},
                rationale="Extract companies from current view",
            )
        return ToolAction(tool_name="stop", params={}, rationale="Stop", is_terminal=True)


@pytest.mark.asyncio
async def test_end_to_end_company_extraction():
    manager = PlaywrightSessionManager()
    async with manager.start() as resources:
        page = resources.page
        file_path = Path(__file__).parent / "sample_page.html"
        await page.goto(file_path.as_uri())

        orchestrator = AgentOrchestrator(
            planner=SingleStepPlanner(),
            tools={"company_extract": CompanyExtractionTool()},
            config=AgentConfig(max_steps=3),
        )

        context = await orchestrator.run(
            goal="Collect company listings",
            url=file_path.as_uri(),
            artifacts={"page": page},
        )

        assert context.extractions, "Expected extractions to be recorded"
        companies = context.extractions[0]["companies"]
        names = {entry["name"] for entry in companies}
        assert any("Company A" in name for name in names)
        assert len(names) >= 2
