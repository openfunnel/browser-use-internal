"""Tool wrappers built on top of the company extraction heuristics."""

from __future__ import annotations

from typing import Optional

from ..extraction import CompanyExtractor
from ..llm.base import TextLLMClient, VisionLLMClient
from ..orchestrator import AgentContext, ToolResult
from .dom import DomToolbox


class CompanyExtractionTool:
    name = "company_extract"

    def __init__(
        self,
        *,
        llm: Optional[TextLLMClient] = None,
        text_llm: Optional[TextLLMClient] = None,
        vision_llm: Optional[VisionLLMClient] = None,
    ) -> None:
        self.text_llm = text_llm or llm
        self.vision_llm = vision_llm

    async def execute(self, context: AgentContext, **params):
        page = context.artifacts.get("page")
        if page is None:
            return ToolResult(success=False, error="No active page bound to context")

        dom = DomToolbox(page)
        extractor = CompanyExtractor(dom, llm=self.text_llm, vision_llm=self.vision_llm)
        last_observation = context.observations[-1] if context.observations else None
        dom_excerpt = None
        if last_observation:
            dom_excerpt = last_observation.get("dom_excerpt")
        screenshot_bytes = context.artifacts.get("last_screenshot_bytes")
        if isinstance(screenshot_bytes, bytearray):
            screenshot_bytes = bytes(screenshot_bytes)
        if not isinstance(screenshot_bytes, (bytes, bytearray)):
            screenshot_bytes = None
        screenshot_mime = context.artifacts.get("last_screenshot_mime", "image/png")

        if self.vision_llm and screenshot_bytes is None:
            try:
                screenshot_bytes = await page.screenshot(full_page=True)
                context.artifacts["last_screenshot_bytes"] = screenshot_bytes
                context.artifacts["last_screenshot_mime"] = "image/png"
            except Exception:  # pylint: disable=broad-except
                screenshot_bytes = None

        records, source = await extractor.extract(
            max_results=params.get("max_results", 25),
            goal=context.goal,
            dom_excerpt=dom_excerpt,
            screenshot_bytes=screenshot_bytes,
            screenshot_mime_type=screenshot_mime,
        )

        extraction_payload = [
            {"name": record.name, "context": record.context} for record in records
        ]
        context.artifacts["last_extraction_count"] = len(extraction_payload)

        debug_events = getattr(extractor, "debug_events", [])
        if not extraction_payload and debug_events:
            for stage, message in debug_events[-3:]:
                context.notes.append(f"company_extract::{stage}: {message}")
        context.notes.append(f"company_extract::source={source}")

        return ToolResult(
            success=True,
            extraction={
                "companies": extraction_payload,
                "count": len(extraction_payload),
                "is_at_bottom": (last_observation or {}).get("is_at_bottom"),
                "source": source,
            },
            data={"debug_events": debug_events} if debug_events else None,
        )


__all__ = ["CompanyExtractionTool"]
