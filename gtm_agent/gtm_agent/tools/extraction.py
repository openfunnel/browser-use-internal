"""Tool wrappers built on top of the company extraction heuristics."""

from __future__ import annotations

from typing import Optional

from ..extraction import CompanyExtractor
from ..llm.base import TextLLMClient
from ..orchestrator import AgentContext, ToolResult
from .dom import DomToolbox


class CompanyExtractionTool:
    name = "company_extract"

    def __init__(self, *, llm: Optional[TextLLMClient] = None) -> None:
        self.llm = llm

    async def execute(self, context: AgentContext, **params):
        page = context.artifacts.get("page")
        if page is None:
            return ToolResult(success=False, error="No active page bound to context")

        dom = DomToolbox(page)
        extractor = CompanyExtractor(dom, self.llm)
        last_observation = context.observations[-1] if context.observations else None
        dom_excerpt = None
        if last_observation:
            dom_excerpt = last_observation.get("dom_excerpt")
        records = await extractor.extract(
            max_results=params.get("max_results", 25),
            goal=context.goal,
            dom_excerpt=dom_excerpt,
        )

        extraction_payload = [
            {"name": record.name, "context": record.context} for record in records
        ]
        return ToolResult(success=True, extraction={"companies": extraction_payload})


__all__ = ["CompanyExtractionTool"]
