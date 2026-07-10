"""
app/tools/intent_extractor.py
──────────────────────────────
Converts a raw natural-language query into a structured SearchIntent.
Uses Claude via the LLM service — not TF-IDF, not keyword matching.
"""
from __future__ import annotations

from app.agent.prompts import INTENT_EXTRACTOR_SYSTEM
from app.models.intent import SearchIntent, SortPriority
from app.services.llm_service import get_llm_service


class IntentExtractor:
    """Stateless — safe to call concurrently."""

    async def extract(self, user_message: str, conversation_context: str = "") -> SearchIntent:
        llm = get_llm_service()

        user_content = user_message
        if conversation_context:
            user_content = (
                f"Conversation context:\n{conversation_context}\n\n"
                f"User message: {user_message}"
            )

        raw = await llm.complete_json(
            messages=[{"role": "user", "content": user_content}],
            system=INTENT_EXTRACTOR_SYSTEM,
            max_tokens=512,
        )

        # Normalise and validate — fill defaults if LLM misses fields
        return SearchIntent(
            query_text=raw.get("query_text", user_message),
            category=raw.get("category"),
            subcategory=raw.get("subcategory"),
            brand=raw.get("brand"),
            keywords=raw.get("keywords", []),
            budget_min=self._safe_float(raw.get("budget_min")),
            budget_max=self._safe_float(raw.get("budget_max")),
            sort_priority=SortPriority(
                raw.get("sort_priority", "best_value")
            ) if raw.get("sort_priority") in SortPriority._value2member_map_ else SortPriority.BEST_VALUE,
            must_have_features=raw.get("must_have_features", []),
            nice_to_have_features=raw.get("nice_to_have_features", []),
            is_urgent=bool(raw.get("is_urgent", False)),
            quantity=raw.get("quantity"),
            preferred_platforms=raw.get("preferred_platforms", []),
            exclude_platforms=raw.get("exclude_platforms", []),
        )

    @staticmethod
    def _safe_float(val: object) -> float | None:
        try:
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None
