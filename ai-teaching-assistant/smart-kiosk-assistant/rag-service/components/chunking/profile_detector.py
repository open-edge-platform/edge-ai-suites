from __future__ import annotations

import json
import logging
import re
from typing import Callable


logger = logging.getLogger(__name__)


_HINT_TABLE: tuple[tuple[tuple[str, ...], str], ...] = (
    (("menu", "qsr", "restaurant", "food", "drink", "beverage", "cafe", "diner"),
     "quick_service_restaurant"),
    (("retail", "store", "product", "catalog", "shop"),
     "retail_store"),
    (("bank", "loan", "deposit", "account"),
     "banking"),
    (("flight", "airline", "boarding", "airport"),
     "airline"),
    (("hospital", "patient", "medical", "clinic", "pharma"),
     "hospital"),
    (("ecommerce", "order", "checkout", "cart"),
     "e_commerce"),
)

_DEFAULT_PROFILE: dict = {
    "domain": "generic",
    "structure": "The document has sections with headings followed by detailed content.",
    "split_guidance": "Split where the topic or section changes significantly.",
}


class DocumentProfileDetector:
    """Two-tier domain detection: a cheap filename hint, then an LLM
    classification of three document samples if no hint matches."""

    def __init__(self, llm_text_generator: Callable[[str, int | None, float | None], str]) -> None:
        self.llm_text_generator = llm_text_generator

    def detect(self, text: str, hint: str | None) -> dict:
        return self.from_hint(hint) or self._detect_from_llm(text)

    @staticmethod
    def from_hint(hint: str | None) -> dict | None:
        if not hint:
            return None
        h = hint.lower()
        for keywords, domain in _HINT_TABLE:
            if any(k in h for k in keywords):
                logger.info(
                    "[CHUNKER] Profile inferred from hint %r -> domain=%s", hint, domain,
                )
                return {
                    "domain": domain,
                    "structure": "The document has sections with headings followed by detailed content.",
                    "split_guidance": "Split where the topic, entity, or section changes significantly.",
                }
        return None

    def _detect_from_llm(self, text: str) -> dict:
        n = len(text)
        if n <= 2000:
            samples = [text]
        else:
            mid = n // 2
            samples = [
                text[:1500],
                text[max(0, mid - 750):mid + 750],
                text[-1500:],
            ]
        sample_block = "\n\n---\n\n".join(
            f"SAMPLE {i + 1}:\n{s}" for i, s in enumerate(samples)
        )
        prompt = (
            "Analyze these excerpts from one document. Return ONLY a JSON object with these exact fields:\n"
            '  "domain": category such as "retail_store", "quick_service_restaurant", '
            '"banking", "airline", "hospital", "e_commerce", "generic"\n'
            '  "structure": one sentence describing how this document is organized '
            '(sections, headings, pattern)\n'
            '  "split_guidance": one sentence on what constitutes a natural chunk boundary '
            'for RAG knowledge retrieval\n\n'
            f"DOCUMENT EXCERPTS:\n{sample_block}\n\n"
            "Return ONLY the JSON object, nothing else."
        )
        try:
            raw = self.llm_text_generator(prompt, 256, 0.0)
            logger.info("[CHUNKER] Profile detection raw: %r", raw[:300])
            match = re.search(r"\{[\s\S]*?\}", raw)
            if match:
                profile = json.loads(match.group(0))
                if {"domain", "structure", "split_guidance"} <= set(profile.keys()):
                    result = {k: str(profile[k]) for k in ("domain", "structure", "split_guidance")}
                    logger.info(
                        "[CHUNKER] Document profile: domain=%s | %s",
                        result["domain"], result["structure"],
                    )
                    return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("[CHUNKER] Profile detection failed (%s), using generic defaults", exc)
        logger.info("[CHUNKER] Using generic document profile")
        return dict(_DEFAULT_PROFILE)
