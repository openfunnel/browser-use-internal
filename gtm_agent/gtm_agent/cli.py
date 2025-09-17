"""Command line entry point for executing the GTM agent."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Dict

import structlog

from .config import AgentConfig, PlaywrightConfig
from .llm.anthropic import AnthropicTextClient
from .llm.prompts import ToolDescriptor
from .orchestrator import AgentOrchestrator
from .playwright_session import PlaywrightSessionManager
from .planners import LLMPlanner
from .tools.extraction import CompanyExtractionTool
from .tools.interaction import ClickSelectorTool, ScrollPageTool
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
    return parser.parse_args()


def build_toolkit(disable_screenshot: bool, text_client: AnthropicTextClient) -> Dict[str, object]:
    return {
        "observe_page": ObservePageTool(include_screenshot=not disable_screenshot, max_dom_chars=18000),
        "click_selector": ClickSelectorTool(),
        "scroll_page": ScrollPageTool(),
        "company_extract": CompanyExtractionTool(llm=text_client),
    }


def build_tool_descriptors() -> list[ToolDescriptor]:
    return [
        ToolDescriptor(
            name="observe_page",
            description="Capture the current page title, URL, DOM excerpt, and optional screenshot",
            arg_schema='{ "max_dom_chars": int, "include_screenshot": bool, "full_page": bool }',
        ),
        ToolDescriptor(
            name="click_selector",
            description="Click an element identified by a CSS selector",
            arg_schema='{ "selector": "string", "wait_after_ms": int }',
        ),
        ToolDescriptor(
            name="scroll_page",
            description="Scroll the page either by a delta or to the bottom",
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

    llm_client = AnthropicTextClient()
    if args.model:
        llm_client.config.text_model = args.model

    config = AgentConfig(max_steps=args.max_steps)
    config.playwright.headless = False#args.headless

    tools = build_toolkit(disable_screenshot=args.no_screenshot, text_client=llm_client)
    planner = LLMPlanner(
        llm=llm_client,
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
