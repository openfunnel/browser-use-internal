"""Command line entry point for executing the GTM agent."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Dict

import structlog

from .config import AgentConfig, PlaywrightConfig
from .llm.anthropic import AnthropicTextClient, AnthropicVisionClient
from .llm.prompts import ToolDescriptor
from .orchestrator import AgentOrchestrator
from .playwright_session import PlaywrightSessionManager
from .planners import LLMPlanner
from .tools.extraction import CompanyExtractionTool
from .tools.interaction import ClickLinkTextTool, ClickSelectorTool, ScrollPageTool
from .tools.observation import ObservePageTool

_LOG = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the GTM browser agent")
    parser.add_argument("url", help="Starting URL for the agent")
    parser.add_argument("goal", help="Natural language goal for the agent")
    parser.add_argument("--headless", action="store_true", help="Run the browser headless")
    parser.add_argument("--max-steps", type=int, default=24, help="Maximum planner steps")
    parser.add_argument("--no-screenshot", action="store_true", help="Disable screenshot capture during observations")
    parser.add_argument("--model", default=None, help="Override text model identifier")
    parser.add_argument("--vision-model", default=None, help="Override vision model identifier")
    return parser.parse_args()


def build_toolkit(
    disable_screenshot: bool,
    text_client: AnthropicTextClient,
    vision_client: AnthropicVisionClient | None,
) -> Dict[str, object]:
    return {
        "observe_page": ObservePageTool(include_screenshot=not disable_screenshot, max_dom_chars=18000),
        "click_selector": ClickSelectorTool(),
        "click_link_text": ClickLinkTextTool(),
        "scroll_page": ScrollPageTool(),
        "company_extract": CompanyExtractionTool(text_llm=text_client, vision_llm=vision_client),
    }


def build_tool_descriptors() -> list[ToolDescriptor]:
    return [
        ToolDescriptor(
            name="observe_page",
            description="Capture page title, DOM excerpt, and scroll metrics (height, position, is_at_bottom)",
            arg_schema='{ "max_dom_chars": int, "include_screenshot": bool, "full_page": bool }',
        ),
        ToolDescriptor(
            name="click_selector",
            description="Click an element identified by a CSS selector",
            arg_schema='{ "selector": "string", "wait_after_ms": int }',
        ),
        ToolDescriptor(
            name="click_link_text",
            description="Click a link using its visible text (used for pagination)",
            arg_schema='{ "link_text": "string", "exact": bool }',
        ),
        ToolDescriptor(
            name="scroll_page",
            description="Scroll by a delta or repeatedly to the bottom until is_at_bottom becomes true",
            arg_schema='{ "mode": "by|bottom", "x": int, "y": int }',
        ),
        ToolDescriptor(
            name="company_extract",
            description="Extract company-like names from visible DOM content",
            arg_schema='{ "max_results": int }',
        ),
    ]


async def run_agent(args: argparse.Namespace) -> int:
    if "ANTHROPIC_API_KEY" not in os.environ:
        _LOG.error("missing_api_key", message="ANTHROPIC_API_KEY environment variable is required")
        return 1

    config = AgentConfig(max_steps=args.max_steps)
    if args.model:
        config.llm.text_model = args.model
        if args.vision_model is None:
            config.llm.vision_model = args.model
    if args.vision_model:
        config.llm.vision_model = args.vision_model
    config.playwright.headless = False#args.headless

    text_client = AnthropicTextClient(config=config.llm)
    vision_client = None
    if config.llm.vision_model:
        vision_client = AnthropicVisionClient(config=config.llm)

    tools = build_toolkit(
        disable_screenshot=args.no_screenshot,
        text_client=text_client,
        vision_client=vision_client,
    )
    planner = LLMPlanner(
        llm=text_client,
        tool_descriptors=build_tool_descriptors(),
    )

    orchestrator = AgentOrchestrator(planner=planner, tools=tools, config=config)

    session_manager = PlaywrightSessionManager(config=config.playwright)

    async with session_manager.start() as resources:
        page = resources.page
        _LOG.info("navigating", url=args.url)
        await page.goto(args.url)
        context = await orchestrator.run(
            goal=args.goal,
            url=args.url,
            artifacts={"page": page},
        )

    payload = {
        "goal": args.goal,
        "url": args.url,
        "step_count": context.step_count,
        "completed": context.completed,
        "extractions": context.extractions,
        "notes": context.notes,
    }

    print(json.dumps(payload, indent=2))
    return 0


def main() -> None:
    structlog.configure(processors=[structlog.processors.JSONRenderer()])
    args = parse_args()
    exit_code = asyncio.run(run_agent(args))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
