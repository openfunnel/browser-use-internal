"""DOM-centric helper tools for the GTM agent."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from playwright.async_api import Page


class DomToolbox:
    """Utility methods for inspecting and extracting DOM data."""

    def __init__(self, page: Page) -> None:
        self.page = page

    async def snapshot(self, *, max_chars: int = 40000) -> str:
        """Return a truncated HTML snapshot for LLM consumption."""

        content = await self.page.content()
        return content[:max_chars]

    async def query_text_all(self, selector: str, *, limit: Optional[int] = None) -> List[str]:
        """Return stripped inner text for all nodes matching selector."""

        handles = await self.page.query_selector_all(selector)
        results: List[str] = []
        for handle in handles:
            text = (await handle.inner_text() or "").strip()
            if text:
                results.append(text)
            if limit is not None and len(results) >= limit:
                break
        return results

    async def query_attributes(self, selector: str, attribute: str) -> List[Optional[str]]:
        """Return requested attribute for all matching elements."""

        values: List[Optional[str]] = await self.page.eval_on_selector_all(
            selector,
            "(nodes, attribute) => nodes.map(node => node.getAttribute(attribute))",
            attribute,
        )
        return values

    async def visible_text(self, selector: str) -> Optional[str]:
        """Return the visible text for the first matching element."""

        element = await self.page.query_selector(selector)
        if element is None:
            return None
        return (await element.inner_text() or "").strip()

    async def serialize_roles(self, roles: List[str], *, limit: int = 10) -> Dict[str, List[str]]:
        """Collect text from semantic roles useful for accessibility-aware scraping."""

        role_map: Dict[str, List[str]] = {}
        for role in roles:
            locators = self.page.get_by_role(role)
            texts = await locators.all_inner_texts()
            cleaned = [text.strip() for text in texts if text and text.strip()]
            role_map[role] = cleaned[:limit]
        return role_map

    async def wait_for_selector(self, selector: str, timeout_ms: Optional[int] = None) -> bool:
        """Wait for selector to appear, returning True if found."""

        try:
            await self.page.wait_for_selector(selector, timeout=timeout_ms)
            return True
        except Exception:
            return False


__all__ = ["DomToolbox"]
