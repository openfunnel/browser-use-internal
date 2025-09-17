"""Observation-oriented tools for page state capture."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from playwright.async_api import Page

from ..orchestrator import AgentContext, ToolResult
from .dom import DomToolbox


class ObservePageTool:
    """Capture DOM snapshot and screenshots for downstream reasoning."""

    name = "observe_page"

    def __init__(self, *, include_screenshot: bool = True, max_dom_chars: int = 20000) -> None:
        self.include_screenshot = include_screenshot
        self.max_dom_chars = max_dom_chars

    async def execute(self, context: AgentContext, **params: Any) -> ToolResult:
        page: Optional[Page] = context.artifacts.get("page")  # type: ignore[assignment]
        if page is None:
            return ToolResult(success=False, error="No active page bound to context")

        dom = DomToolbox(page)
        max_chars = int(params.get("max_dom_chars", self.max_dom_chars))
        snapshot = await dom.snapshot(max_chars=max_chars)
        title = await page.title()
        url = page.url

        scroll_height, viewport_height, scroll_y = await asyncio.gather(
            page.evaluate("() => document.scrollingElement.scrollHeight"),
            page.evaluate("() => window.innerHeight"),
            page.evaluate("() => window.scrollY"),
        )
        is_at_bottom = (scroll_y + viewport_height) >= (scroll_height - 4)

        observation: Dict[str, Any] = {
            "type": "page_state",
            "url": url,
            "title": title,
            "dom_excerpt": snapshot,
            "scroll_height": scroll_height,
            "viewport_height": viewport_height,
            "scroll_y": scroll_y,
            "is_at_bottom": is_at_bottom,
        }

        if self.include_screenshot or params.get("include_screenshot"):
            screenshot_bytes = await page.screenshot(full_page=params.get("full_page", False))
            context.artifacts["last_screenshot_bytes"] = screenshot_bytes
            observation["screenshot_available"] = True

        return ToolResult(success=True, observation=observation)


__all__ = ["ObservePageTool"]
