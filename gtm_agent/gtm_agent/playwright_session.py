"""Playwright session management helpers."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import AsyncIterator

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from .config import PlaywrightConfig


@dataclass
class PlaywrightResources:
    """Encapsulates the Playwright primitives for convenient teardown."""

    playwright: Playwright
    browser: Browser
    context: BrowserContext
    page: Page


class PlaywrightSessionManager:
    """Starts and stops Playwright sessions based on agent configuration."""

    def __init__(self, config: PlaywrightConfig | None = None) -> None:
        self.config = config or PlaywrightConfig()

    @contextlib.asynccontextmanager
    async def start(self) -> AsyncIterator[PlaywrightResources]:
        resources = await self._launch()
        try:
            yield resources
        finally:
            await self._close(resources)

    async def create_page(self) -> PlaywrightResources:
        """Convenience helper returning ready-to-use page with manual cleanup."""

        return await self._launch()

    async def _launch(self) -> PlaywrightResources:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=self.config.headless,
            slow_mo=self.config.slow_mo_ms,
        )
        context = await browser.new_context(
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            }
        )
        page = await context.new_page()

        timeout_ms = getattr(self.config, "navigation_timeout_ms", None)
        if timeout_ms is not None:
            page.set_default_timeout(timeout_ms)
            page.set_default_navigation_timeout(timeout_ms)

        return PlaywrightResources(playwright=playwright, browser=browser, context=context, page=page)

    async def _close(self, resources: PlaywrightResources) -> None:
        await resources.page.close()
        await resources.context.close()
        await resources.browser.close()
        await resources.playwright.stop()


__all__ = ["PlaywrightSessionManager", "PlaywrightResources"]
