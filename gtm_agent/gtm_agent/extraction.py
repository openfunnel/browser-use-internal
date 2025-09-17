"""Company extraction heuristics and helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import structlog
from typing import Iterable, List, Optional, Sequence, Set

from .llm.base import TextLLMClient, VisionLLMClient
from .llm.types import ChatMessage, LLMResult, VisionPrompt
from .tools.dom import DomToolbox

_LOG = structlog.get_logger(__name__)

_PRIMARY_SELECTORS: Sequence[str] = (
    "[data-company]",
    "[data-company-name]",
    ".company",
    ".company-name",
    ".CompanyName",
    "article h2",
    "article h3",
    "section h2",
    "section h3",
    "h2",
    "h3",
    "table td:first-child",
    "table td:first-of-type",
    "tbody td:first-child",
    "tbody tr td:first-child",
    "li",
    "[role='listitem']",
)


@dataclass
class CompanyRecord:
    name: str
    context: Optional[str] = None


class CompanyExtractor:
    """Collects candidate strings using DOM heuristics and optional LLM cleanup."""

    def __init__(
        self,
        dom: DomToolbox,
        llm: Optional[TextLLMClient] = None,
        vision_llm: Optional[VisionLLMClient] = None,
    ) -> None:
        self.dom = dom
        self.llm = llm
        self.vision_llm = vision_llm
        self.debug_events: list[tuple[str, str]] = []

    async def extract(
        self,
        *,
        max_results: int = 25,
        goal: Optional[str] = None,
        dom_excerpt: Optional[str] = None,
        screenshot_bytes: Optional[bytes] = None,
        screenshot_mime_type: str = "image/png",
    ) -> tuple[List[CompanyRecord], str]:
        candidates = await self._collect_candidates()
        unique = self._dedupe(candidates)

        combined = list(unique)

        if self.vision_llm and screenshot_bytes:
            vision_records, vision_source = await self._extract_with_vision(
                screenshot_bytes,
                mime_type=screenshot_mime_type,
                goal=goal,
                max_results=max_results,
            )
            if vision_records:
                combined = self._merge_records(combined, vision_records)
                return combined[:max_results], vision_source

        if self.llm:
            if combined:
                refined = await self._refine_with_llm(
                    combined,
                    max_results=max_results,
                    goal=goal,
                    dom_excerpt=dom_excerpt,
                )
                if refined:
                    return refined[:max_results], "dom_llm_refine"
            elif dom_excerpt:
                direct, dom_source = await self._extract_from_dom(
                    dom_excerpt,
                    max_results=max_results,
                    goal=goal,
                )
                if direct:
                    return direct[:max_results], dom_source

        return combined[:max_results], "dom_heuristic"

    def _debug(self, stage: str, message: str) -> None:
        preview = message.strip()
        if len(preview) > 400:
            preview = preview[:397] + "..."
        self.debug_events.append((stage, preview))

    async def _collect_candidates(self) -> List[CompanyRecord]:
        collected: List[CompanyRecord] = []
        seen_text: Set[str] = set()

        for selector in _PRIMARY_SELECTORS:
            texts = await self.dom.query_text_all(selector, limit=120)
            for text in texts:
                normalized = self._normalize(text)
                if not normalized or normalized in seen_text:
                    continue
                if len(normalized) > 320:
                    normalized = normalized[:320].rstrip(",;: ")
                seen_text.add(normalized)
                name, context = self._split_name_context(normalized)
                if self._looks_like_company(name):
                    collected.append(CompanyRecord(name=name, context=context))
        return collected

    def _dedupe(self, records: Iterable[CompanyRecord]) -> List[CompanyRecord]:
        unique: List[CompanyRecord] = []
        seen: Set[str] = set()
        for record in records:
            key = record.name.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(record)
        return unique

    def _merge_records(
        self, existing: List[CompanyRecord], new_records: List[CompanyRecord]
    ) -> List[CompanyRecord]:
        combined = list(existing)
        seen = {record.name.lower() for record in existing}
        for record in new_records:
            key = record.name.lower()
            if key in seen:
                continue
            seen.add(key)
            combined.append(record)
        return combined

    async def _refine_with_llm(
        self,
        records: List[CompanyRecord],
        *,
        max_results: int,
        goal: Optional[str],
        dom_excerpt: Optional[str],
    ) -> List[CompanyRecord]:
        payload = "\n".join(
            f"- Name: {record.name}\n  Context: {record.context or 'n/a'}" for record in records
        )
        task = goal or "Extract relevant company or organization names."
        dom_snippet = ""
        if dom_excerpt:
            truncated = dom_excerpt[:6000]
            dom_snippet = f"\nDOM excerpt:\n{truncated}"
        messages = [
            ChatMessage(
                role="system",
                content=(
                    "You clean noisy text snippets from web pages. "
                    "Return a JSON array of objects with keys 'name' and optional 'context'. "
                    "Strip numbering, ranking prefixes, vote counts, and similar metadata. "
                    "Skip items that are navigation links or contain phrases like 'points by', 'comments', or 'login'."
                ),
            ),
            ChatMessage(
                role="user",
                content=(
                    "Goal: {task}\n"
                    "Return up to {max_results} relevant entries as JSON array with keys 'name' and optional 'context'.\n"
                    "If nothing fits, reply with [].\n"
                    "Candidates:\n"
                    "{payload}{dom_snippet}"
                ).format(task=task, max_results=max_results, payload=payload, dom_snippet=dom_snippet),
            ),
        ]

        try:
            result: LLMResult = await self.llm.complete(messages, max_tokens=768, temperature=0.0)  # type: ignore[arg-type]
        except Exception as exc:
            _LOG.warning("extraction_llm_call_failed", error=str(exc))
            self._debug("llm_refine_error", str(exc))
            return records

        refined = self._parse_llm_response(result.text, fallback=records)
        self._debug("llm_refine_response", result.text)
        if refined is records:
            _LOG.info("extraction_llm_fallback", preview=result.text[:400])
        return refined

    async def _extract_with_vision(
        self,
        screenshot_bytes: bytes,
        *,
        mime_type: str,
        goal: Optional[str],
        max_results: int,
    ) -> tuple[List[CompanyRecord], str]:
        if not self.vision_llm:
            return [], "vision_unavailable"

        task = goal or "Identify company or organization names from the first column of the visible listings."
        prompt = (
            "You are looking at a webpage screenshot. "
            "Extract the company or organization names visible in the first column of any table or list related to filings. "
            "Return up to {max_results} results as a JSON array of objects with keys 'name' and optional 'context'. "
            "If nothing fits, return []."
        ).format(max_results=max_results)

        payload = VisionPrompt(
            prompt=f"Goal: {task}",
            image_bytes=screenshot_bytes,
            mime_type=mime_type,
            max_tokens=700,
        )

        try:
            result: LLMResult = await self.vision_llm.describe(payload)
        except Exception as exc:  # pylint: disable=broad-except
            _LOG.warning("extraction_vision_call_failed", error=str(exc))
            self._debug("vision_error", str(exc))
            return [], "vision_error"

        records = self._parse_llm_response(result.text, fallback=[])
        self._debug("vision_response", result.text)
        if records:
            return records[:max_results], "vision_json"

        converted = await self._convert_text_to_records(
            result.text,
            max_results=max_results,
            goal=goal,
            source="vision",
        )
        if converted:
            return converted[:max_results], "vision_llm"

        return [], "vision_empty"

    async def _extract_from_dom(
        self,
        dom_excerpt: str,
        *,
        max_results: int,
        goal: Optional[str],
    ) -> tuple[List[CompanyRecord], str]:
        records = await self._convert_text_to_records(
            dom_excerpt,
            max_results=max_results,
            goal=goal,
            source="dom",
        )
        return records, "dom_llm"

    async def _convert_text_to_records(
        self,
        text: str,
        *,
        max_results: int,
        goal: Optional[str],
        source: str,
    ) -> List[CompanyRecord]:
        if not self.llm:
            return []

        snippet = text[:12000]
        task = goal or "Identify company or organization names from the provided content."
        messages = [
            ChatMessage(
                role="system",
                content=(
                    "You normalize unstructured web content into structured JSON. "
                    "Return a JSON array of objects with keys 'name' and optional 'context' "
                    "containing company or customer names referenced in case studies. "
                    "Skip navigation, footer links, and generic headings."
                ),
            ),
            ChatMessage(
                role="user",
                content=(
                    "Goal: {task}\n"
                    "Return up to {max_results} relevant entries as JSON array with keys 'name' and optional 'context'.\n"
                    "If nothing fits, reply with [].\n"
                    "Source ({source}) snippet:\n{snippet}"
                ).format(task=task, max_results=max_results, snippet=snippet, source=source),
            ),
        ]

        try:
            result: LLMResult = await self.llm.complete(messages, max_tokens=900, temperature=0.0)  # type: ignore[arg-type]
        except Exception as exc:  # pylint: disable=broad-except
            _LOG.warning(f"extraction_{source}_llm_call_failed", error=str(exc))
            self._debug(f"{source}_llm_error", str(exc))
            return []

        records = self._parse_llm_response(result.text, fallback=[])
        self._debug(f"{source}_llm_response", result.text)
        return records[:max_results]

    def _clean_name(self, text: str) -> str:
        cleaned = re.sub(r"^\d+[\.)-]*\s*", "", text)
        cleaned = re.sub(r"^[-•\s]+", "", cleaned)
        return cleaned.strip()

    def _parse_llm_response(self, text: str, *, fallback: List[CompanyRecord]) -> List[CompanyRecord]:
        cleaned = text.strip()
        if not cleaned:
            return fallback

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("[")
            end = cleaned.rfind("]")
            if start != -1 and end != -1 and end > start:
                try:
                    data = json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    return fallback
            else:
                return fallback

        parsed: List[CompanyRecord] = []
        seen: Set[str] = set()
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                name = self._normalize(str(item.get("name", "")))
                name = self._clean_name(name)
                if not name:
                    continue
                lower_name = name.lower()
                if lower_name.startswith("hacker news"):
                    continue
                context_value = item.get("context")
                context = self._normalize(str(context_value)) if context_value else None
                if not self._looks_like_company(name):
                    continue
                if lower_name in seen:
                    continue
                seen.add(lower_name)
                parsed.append(CompanyRecord(name=name, context=context))
        return parsed or fallback

    def _normalize(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text or "").strip()
        return cleaned

    def _split_name_context(self, text: str) -> tuple[str, Optional[str]]:
        for delimiter in ("—", " - ", " -", "- ", "|", "·"):
            if delimiter in text:
                name, context = text.split(delimiter, 1)
                return name.strip(), context.strip()
        if "  " in text:
            name, context = text.split("  ", 1)
            return name.strip(), context.strip()
        return text, None

    def _looks_like_company(self, text: str) -> bool:
        if not text:
            return False
        if len(text) > 180 or len(text) < 2:
            return False
        lower = text.lower()
        if any(token in lower for token in ("http", "@", "copyright", "privacy", "login")):
            return False
        if "points by" in lower or "comments" in lower:
            return False
        if "hacker news" in lower:
            return False
        if lower in {"past", "ask", "show", "jobs", "submit", "guidelines"}:
            return False
        if "name date filed" in lower:
            return False
        capitalized_words = sum(1 for token in re.findall(r"[A-Za-z]+", text) if token[0].isupper())
        return capitalized_words >= 1


__all__ = ["CompanyExtractor", "CompanyRecord"]
