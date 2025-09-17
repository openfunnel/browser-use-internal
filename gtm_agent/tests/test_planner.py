import pytest

from gtm_agent.llm.prompts import PlannerPromptBuilder, ToolDescriptor
from gtm_agent.orchestrator import AgentConfig, AgentContext
from gtm_agent.planners import LLMPlanner


class StubLLM:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls = 0

    async def complete(self, messages, *, max_tokens, temperature):
        self.calls += 1
        return type("Result", (), {"text": self.response_text})


def build_context() -> AgentContext:
    config = AgentConfig()
    context = AgentContext(goal="Collect companies", url="https://example.com", config=config)
    context.notes.extend(["Initial note"])
    context.add_observation({"dom_excerpt": "<div>"})
    return context


@pytest.mark.asyncio
async def test_llm_planner_parses_json_payload():
    response = """```json
{"tool_name": "observe_page", "params": {"max_dom_chars": 1000}, "rationale": "Need fresh DOM"}
```"""
    planner = LLMPlanner(
        llm=StubLLM(response),
        tool_descriptors=[ToolDescriptor(name="observe_page", description="Snapshot the DOM")],
        prompt_builder=PlannerPromptBuilder("system"),
    )

    action = await planner.select_action(build_context())
    assert action.tool_name == "observe_page"
    assert action.params == {"max_dom_chars": 1000}
    assert not action.is_terminal


@pytest.mark.asyncio
async def test_llm_planner_handles_invalid_json():
    response = "No JSON available"
    planner = LLMPlanner(
        llm=StubLLM(response),
        tool_descriptors=[],
    )

    action = await planner.select_action(build_context())
    assert action.is_terminal
    assert action.tool_name == "stop"
