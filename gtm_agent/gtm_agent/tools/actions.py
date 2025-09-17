"""Page interaction helpers built on top of Playwright."""

from __future__ import annotations

import asyncio
from typing import Optional

from playwright.async_api import Page


class ActionToolbox:
    """Collection of reusable high-level browser actions."""

    def __init__(self, page: Page) -> None:
        self.page = page

    async def click(self, selector: str, *, timeout_ms: Optional[int] = None, click_delay_ms: int = 0) -> None:
        await self.page.click(selector, timeout=timeout_ms, delay=click_delay_ms)

    async def type_text(self, selector: str, text: str, *, delay_ms: int = 20, clear_first: bool = True) -> None:
        locator = self.page.locator(selector)
        if clear_first:
            await locator.fill("", timeout=self.page.timeout)
        await locator.type(text, delay=delay_ms)

    async def press_key(self, key: str) -> None:
        await self.page.keyboard.press(key)

    async def wait_for_network_idle(self, *, timeout_ms: Optional[int] = None) -> None:
        await self.page.wait_for_load_state("networkidle", timeout=timeout_ms)

    async def scroll_to_bottom(self, *, step_px: int = 400, delay_ms: int = 100, max_iterations: int = 50) -> int:
        last_height = 0
        for _ in range(max_iterations):
            await self.page.mouse.wheel(0, step_px)
            await asyncio.sleep(delay_ms / 1000)
            new_height = await self.page.evaluate("() => document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        return last_height

    async def scroll_by(self, *, x: int = 0, y: int = 400) -> None:
        await self.page.evaluate("({ x, y }) => window.scrollBy(x, y)", {"x": x, "y": y})


__all__ = ["ActionToolbox"]
