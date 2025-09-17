"""Prompt utilities for orchestrating LLM calls."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .types import ChatMessage


@dataclass
class ToolDescriptor:
    name: str
    description: str
    arg_schema: str | None = None


class PlannerPromptBuilder:
    """Builds planner prompts combining observations, notes, and tool metadata."""

    def __init__(self, system_prompt: str | None = None) -> None:
        self.system_prompt = system_prompt or (
            "You are a browsing automation planner coordinating a single-page agent."
            " Always keep the user goal in mind."
            " Inspect the page with observe_page before acting, use click/scroll to navigate,"
            " and when the requested information is visible call company_extract to collect it."
            " Avoid looping on the same tool/arguments without progress."
        )

    def build(
        self,
        *,
        goal: str,
        url: str,
        notes: Sequence[str],
        observations: Sequence[dict],
        tools: Iterable[ToolDescriptor],
    ) -> List[ChatMessage]:
        messages: List[ChatMessage] = [ChatMessage(role="system", content=self.system_prompt)]

        tool_overview = "\n".join(
            f"- {tool.name}: {tool.description}" + (f" Args: {tool.arg_schema}" if tool.arg_schema else "")
            for tool in tools
        ) or "- No tools registered"

        note_text = "\n".join(f"- {note}" for note in notes[-5:]) or "- None"
        observation_text = "\n".join(
            f"{idx}. {json.dumps(obs, ensure_ascii=False)[:400]}"
            for idx, obs in enumerate(observations[-3:], start=1)
        ) or "1. {}"

        user_prompt = (
            "Plan the next action for the browsing agent."
            f"\nGoal: {goal}"
            f"\nCurrent URL: {url}"
            "\nRecent Notes:\n"
            f"{note_text}"
            "\nRecent Observations:\n"
            f"{observation_text}"
            "\nAvailable Tools:\n"
            f"{tool_overview}"
            "\nRespond in JSON with keys 'tool_name', 'params', and optional 'stop'."
        )

        messages.append(ChatMessage(role="user", content=user_prompt))
        return messages


__all__ = ["PlannerPromptBuilder", "ToolDescriptor"]
