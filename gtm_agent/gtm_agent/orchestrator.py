"""Core orchestration loop for the GTM agent."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Dict, List, Optional, Protocol

from .config import AgentConfig


@dataclass
class AgentContext:
    """Mutable state shared across the agent loop."""

    goal: str
    url: str
    config: AgentConfig
    step_count: int = 0
    completed: bool = False
    notes: List[str] = field(default_factory=list)
    observations: List[Dict[str, Any]] = field(default_factory=list)
    extractions: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)

    def add_observation(self, observation: Dict[str, Any]) -> None:
        self.observations.append(observation)

    def add_extraction(self, extraction: Dict[str, Any]) -> None:
        self.extractions.append(extraction)


@dataclass
class ToolAction:
    """Planner-selected action describing the next tool invocation."""

    tool_name: str
    params: Dict[str, Any]
    rationale: str = ""
    is_terminal: bool = False


@dataclass
class ToolResult:
    """Canonical tool result returned to the orchestrator."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    observation: Optional[Dict[str, Any]] = None
    extraction: Optional[Dict[str, Any]] = None


class Planner(Protocol):
    """Planner decides which tool to run next."""

    async def select_action(self, context: AgentContext) -> ToolAction:
        """Return the next tool action to execute."""


class Tool(Protocol):
    """Executable tool interface."""

    name: str

    async def execute(self, context: AgentContext, **params: Any) -> ToolResult:
        """Execute the tool and return a result."""


class AgentOrchestrator:
    """Drives the observe → reason → act loop using registered tools."""

    def __init__(self, *, planner: Planner, tools: Dict[str, Tool], config: Optional[AgentConfig] = None) -> None:
        self.planner = planner
        self.tools = tools
        self.config = config or AgentConfig()

    async def run(self, goal: str, url: str, *, artifacts: dict[str, object] | None = None) -> AgentContext:
        context = AgentContext(goal=goal, url=url, config=self.config)
        if artifacts:
            context.artifacts.update(artifacts)

        while not context.completed and context.step_count < self.config.max_steps:
            action = await self.planner.select_action(context)
            rationale_note = action.rationale or f"Planner chose {action.tool_name}"
            context.notes.append(rationale_note)

            if action.is_terminal:
                context.completed = True
                break

            tool = self.tools.get(action.tool_name)
            if tool is None:
                context.notes.append(f"Planner selected unknown tool: {action.tool_name}")
                break

            result = await tool.execute(context, **action.params)
            context.step_count += 1

            action_summary = f"Executed {tool.name} with params {action.params}"
            if result.success:
                context.notes.append(action_summary + " -> success")
            else:
                context.notes.append(action_summary + f" -> failure: {result.error or 'unknown error'}")

            if result.observation:
                context.add_observation(result.observation)
            if result.extraction:
                context.add_extraction(result.extraction)
            if not result.success:
                break

            await self._apply_throttling()

        context.completed = context.completed or context.step_count >= self.config.max_steps
        return context

    async def _apply_throttling(self) -> None:
        """Simple async hook to let the event loop breathe between steps."""

        await asyncio.sleep(0)


__all__ = [
    "AgentContext",
    "AgentOrchestrator",
    "ToolAction",
    "ToolResult",
    "Planner",
    "Tool",
]
