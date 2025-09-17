import asyncio

from gtm_agent.config import AgentConfig
from gtm_agent.orchestrator import AgentOrchestrator, ToolAction, ToolResult


class DummyPlanner:
    def __init__(self) -> None:
        self.calls = 0

    async def select_action(self, context):
        if self.calls == 0:
            self.calls += 1
            return ToolAction(
                tool_name="mock",
                params={"payload": "company"},
                rationale="Collect initial observation",
            )
        return ToolAction(tool_name="mock", params={}, rationale="Stop", is_terminal=True)


class DummyTool:
    name = "mock"

    async def execute(self, context, **params):
        payload = params.get("payload")
        observation = {"payload": payload}
        extraction = {"name": payload, "context": "example"}
        return ToolResult(success=True, observation=observation, extraction=extraction)


def test_orchestrator_runs_until_planner_signals_stop():
    orchestrator = AgentOrchestrator(
        planner=DummyPlanner(),
        tools={"mock": DummyTool()},
        config=AgentConfig(max_steps=3),
    )

    context = asyncio.run(orchestrator.run(goal="Collect companies", url="https://example.com"))

    assert context.step_count == 1
    assert context.extractions == [{"name": "company", "context": "example"}]
    assert context.observations == [{"payload": "company"}]
    assert context.notes[0] == "Collect initial observation"


class FailingTool:
    name = "failing"

    async def execute(self, context, **params):
        return ToolResult(success=False, error="boom")


class FailPlanner:
    async def select_action(self, context):
        return ToolAction(tool_name="failing", params={}, rationale="Try failing tool")


def test_orchestrator_records_failures():
    orchestrator = AgentOrchestrator(
        planner=FailPlanner(),
        tools={"failing": FailingTool()},
        config=AgentConfig(max_steps=2),
    )

    context = asyncio.run(orchestrator.run(goal="Collect companies", url="https://example.com"))

    assert context.step_count == 1
    assert not context.extractions
    assert "failure" in context.notes[-1]
