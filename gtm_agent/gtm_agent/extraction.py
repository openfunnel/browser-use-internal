"""Company extraction heuristics and helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import structlog
from typing import Iterable, List, Optional, Sequence, Set

from .llm.base import TextLLMClient
from .llm.types import ChatMessage, LLMResult
from .tools.dom import DomToolbox

_LOG = structlog.get_logger(__name__)

_PRIMARY_SELECTORS: Sequence[str] = (
    "[data-company]",
    "[data-company-name]",
    ".company",
    ".company-name",
    ".CompanyName",
    "li",
    "tbody tr",
    "[role='listitem']",
    "table tr",
)


@dataclass
class CompanyRecord:
    name: str
    context: Optional[str] = None


class CompanyExtractor:
    """Collects candidate strings using DOM heuristics and optional LLM cleanup."""

    def __init__(self, dom: DomToolbox, llm: Optional[TextLLMClient] = None) -> None:
        self.dom = dom
        self.llm = llm

    async def extract(
        self,
        *,
        max_results: int = 25,
        goal: Optional[str] = None,
        dom_excerpt: Optional[str] = None,
    ) -> List[CompanyRecord]:
        candidates = await self._collect_candidates()
        unique = self._dedupe(candidates)

        if self.llm and unique:
            refined = await self._refine_with_llm(
                unique,
                max_results=max_results,
                goal=goal,
                dom_excerpt=dom_excerpt,
            )
            if refined:
                return refined[:max_results]

        return unique[:max_results]

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
            return records

        refined = self._parse_llm_response(result.text, fallback=records)
        if refined is records:
            _LOG.info("extraction_llm_fallback", preview=result.text[:400])
        return refined

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
        capitalized_words = sum(1 for token in re.findall(r"[A-Za-z]+", text) if token[0].isupper())
        return capitalized_words >= 1


__all__ = ["CompanyExtractor", "CompanyRecord"]
