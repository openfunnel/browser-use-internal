"""LLM-backed planner that selects tools for the agent."""

from __future__ import annotations

import json
import re
from typing import Iterable, List, Mapping, Sequence

import structlog

from ..llm.base import TextLLMClient
from ..llm.prompts import PlannerPromptBuilder, ToolDescriptor
from ..llm.types import ChatMessage
from ..orchestrator import AgentContext, ToolAction

_LOG = structlog.get_logger(__name__)


class LLMPlanner:
    """Planner that delegates decision making to a text LLM."""

    def __init__(
        self,
        *,
        llm: TextLLMClient,
        tool_descriptors: Iterable[ToolDescriptor],
        prompt_builder: PlannerPromptBuilder | None = None,
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> None:
        self.llm = llm
        self.prompt_builder = prompt_builder or PlannerPromptBuilder()
        self.tool_descriptors = list(tool_descriptors)
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def select_action(self, context: AgentContext) -> ToolAction:
        messages = self._build_messages(context)
        response = await self.llm.complete(messages, max_tokens=self.max_tokens, temperature=self.temperature)
        action_payload = self._parse_response(response.text)
        _LOG.info("planner_response", text=response.text[:400], payload=action_payload)

        if action_payload is None:
            _LOG.warning("planner_failed_to_parse", text=response.text)
            return ToolAction(tool_name="stop", params={}, rationale="LLM response could not be parsed", is_terminal=True)

        tool_name = action_payload.get("tool_name")
        params = action_payload.get("params", {})
        rationale = action_payload.get("rationale", "")
        is_terminal = bool(action_payload.get("stop")) or tool_name in (None, "stop")

        if (tool_name is None or not isinstance(params, dict)) and not is_terminal:
            _LOG.warning("planner_missing_fields", payload=action_payload)
            return ToolAction(tool_name="stop", params={}, rationale="Planner returned incomplete payload", is_terminal=True)

        if is_terminal:
            return ToolAction(tool_name="stop", params={}, rationale=rationale or "Planner requested stop", is_terminal=True)

        return ToolAction(tool_name=str(tool_name), params=params, rationale=rationale)

    def _build_messages(self, context: AgentContext) -> Sequence[ChatMessage]:
        return self.prompt_builder.build(
            goal=context.goal,
            url=context.url,
            notes=context.notes,
            observations=context.observations,
            tools=self.tool_descriptors,
        )

    def _parse_response(self, text: str) -> Mapping[str, object] | None:
        cleaned = self._extract_json_block(text)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            return None

        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list) and payload:
            return payload[0] if isinstance(payload[0], dict) else None
        return None

    def _extract_json_block(self, text: str) -> str:
        code_block = re.search(r"```json\s*(?P<body>.+?)```", text, flags=re.DOTALL)
        if code_block:
            return code_block.group("body").strip()

        brace_start = text.find("{")
        if brace_start != -1:
            brace_level = 0
            for idx, char in enumerate(text[brace_start:], start=brace_start):
                if char == "{":
                    brace_level += 1
                elif char == "}":
                    brace_level -= 1
                    if brace_level == 0:
                        return text[brace_start : idx + 1]
        bracket_start = text.find("[")
        if bracket_start != -1:
            brace_level = 0
            for idx, char in enumerate(text[bracket_start:], start=bracket_start):
                if char == "[":
                    brace_level += 1
                elif char == "]":
                    brace_level -= 1
                    if brace_level == 0:
                        return text[bracket_start : idx + 1]
        return text.strip()


__all__ = ["LLMPlanner"]
