"""Configuration models for the GTM web scraping agent."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LLMConfig:
    """Configurable properties for LLM clients."""

    text_model: str = "claude-3-5-sonnet-20241022"
    vision_model: Optional[str] = "claude-3-5-sonnet-20241022"
    max_tokens: int = 4000
    temperature: float = 0.2


@dataclass
class PlaywrightConfig:
    """Settings for Playwright browser sessions."""

    headless: bool = False
    slow_mo_ms: Optional[int] = None
    viewport_width: int = 1280
    viewport_height: int = 720
    navigation_timeout_ms: int = 10000


@dataclass
class AgentConfig:
    """Top-level configuration object for the GTM agent."""

    max_steps: int = 24
    navigation_timeout_ms: int = 10000
    llm: LLMConfig = field(default_factory=LLMConfig)
    playwright: PlaywrightConfig = field(default_factory=PlaywrightConfig)
    extraction_fields: List[str] = field(default_factory=lambda: ["name", "context"])


__all__ = ["AgentConfig", "LLMConfig", "PlaywrightConfig"]
