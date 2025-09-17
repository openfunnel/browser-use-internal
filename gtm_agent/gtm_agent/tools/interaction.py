"""Interaction tools enabling the planner to manipulate the page."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from playwright.async_api import Page

from ..orchestrator import AgentContext, ToolResult
from .actions import ActionToolbox


class ClickSelectorTool:
    """Click an element identified by a CSS selector."""

    name = "click_selector"

    async def execute(self, context: AgentContext, **params: Any) -> ToolResult:
        selector = params.get("selector")
        if not selector:
            return ToolResult(success=False, error="Missing 'selector' parameter")

        page: Optional[Page] = context.artifacts.get("page")  # type: ignore[assignment]
        if page is None:
            return ToolResult(success=False, error="No active page bound to context")

        timeout_ms = params.get("timeout_ms")
        delay_ms = params.get("click_delay_ms", 0)

        actions = ActionToolbox(page)
        try:
            await actions.click(selector, timeout_ms=timeout_ms, click_delay_ms=delay_ms)
            wait_ms = params.get("wait_after_ms", 250)
            if wait_ms:
                await asyncio.sleep(wait_ms / 1000)
        except Exception as exc:  # pylint: disable=broad-except
            return ToolResult(success=False, error=str(exc))

        observation = {"event": "click", "selector": selector}
        return ToolResult(success=True, observation=observation)


class ClickLinkTextTool:
    """Click a link based on its visible text."""

    name = "click_link_text"

    async def execute(self, context: AgentContext, **params: Any) -> ToolResult:
        link_text = params.get("link_text")
        if not link_text:
            return ToolResult(success=False, error="Missing 'link_text' parameter")

        page: Optional[Page] = context.artifacts.get("page")  # type: ignore[assignment]
        if page is None:
            return ToolResult(success=False, error="No active page bound to context")

        exact = params.get("exact", False)
        wait_ms = int(params.get("wait_after_ms", 1000))

        try:
            locator = page.get_by_role("link", name=link_text, exact=exact)
            count = await locator.count()
            if count == 0:
                locator = page.get_by_text(link_text, exact=exact)
            await locator.first.click()
            if wait_ms:
                await asyncio.sleep(wait_ms / 1000)
        except Exception as exc:  # pylint: disable=broad-except
            return ToolResult(success=False, error=str(exc))

        context.artifacts.setdefault("visited_pagination", set()).add(
            params.get("candidate_key") or link_text
        )
        context.artifacts["pending_observe"] = True
        observation = {"event": "click_link", "link_text": link_text}
        return ToolResult(success=True, observation=observation)


class ScrollPageTool:
    """Scroll the page by a configurable amount or to bottom."""

    name = "scroll_page"

    async def execute(self, context: AgentContext, **params: Any) -> ToolResult:
        page: Optional[Page] = context.artifacts.get("page")  # type: ignore[assignment]
        if page is None:
            return ToolResult(success=False, error="No active page bound to context")

        actions = ActionToolbox(page)
        mode = params.get("mode", "by")

        try:
            if mode == "bottom":
                scroll_info = await actions.scroll_to_bottom(
                    step_px=int(params.get("step_px", 400)),
                    delay_ms=int(params.get("delay_ms", 100)),
                    max_iterations=int(params.get("max_iterations", 30)),
                )
                observation = {"event": "scroll_bottom", **scroll_info}
                context.artifacts["pending_observe"] = True
            else:
                await actions.scroll_by(
                    x=int(params.get("x", 0)),
                    y=int(params.get("y", 400)),
                )
                scroll_state = await actions.scroll_to_bottom(step_px=0, delay_ms=0, max_iterations=0)
                observation = {
                    "event": "scroll",
                    "x": params.get("x", 0),
                    "y": params.get("y", 400),
                    "scroll_height": scroll_state["scroll_height"],
                    "scroll_y": scroll_state["scroll_y"],
                    "viewport_height": scroll_state["viewport_height"],
                    "at_bottom": scroll_state["at_bottom"],
                }
                wait_ms = params.get("wait_after_ms", 200)
                if wait_ms:
                    await asyncio.sleep(wait_ms / 1000)
                context.artifacts["pending_observe"] = True
        except Exception as exc:  # pylint: disable=broad-except
            return ToolResult(success=False, error=str(exc))

        return ToolResult(success=True, observation=observation)


__all__ = ["ClickSelectorTool", "ScrollPageTool"]
