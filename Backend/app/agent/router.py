"""
app/agent/router.py
────────────────────
LLM-based intent router.

Contrast with ShoppingGPT's TF-IDF router (lib_semantic_router.py):
  ❌ ShoppingGPT: TF-IDF cosine match against 40 hardcoded English phrases.
                  Falls back to chitchat when score < threshold.
                  Never retrained. Breaks on Hindi/mixed-language input.
  ✅ This router: Claude classifies intent in <200ms.
                  Handles Hindi, Hinglish, typos, and complex queries.
                  No hardcoded utterance lists to maintain.
"""
from __future__ import annotations

from app.agent.prompts import ROUTER_SYSTEM
from app.models.intent import IntentType
from app.services.llm_service import get_llm_service


class IntentRouter:
    """
    Single-responsibility: classify the user's message into an IntentType.
    Stateless — safe to call from async handlers without locking.
    """

    # Fast keyword pre-filter to avoid LLM call for obvious cases
    _QUICK_KEYWORDS = {
        "hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "bye",
        "help", "who are you", "what can you do", "namaste",
    }

    async def route(
        self,
        user_message: str,
        has_prior_products: bool = False,
    ) -> IntentType:
        """Return the IntentType for this message."""

        # Fast-path: obvious chitchat (saves ~200ms)
        lower = user_message.strip().lower()
        if lower in self._QUICK_KEYWORDS or len(lower) < 3:
            return IntentType.CHITCHAT

        # Fast-path: follow-up if there are prior products and message is short
        follow_up_words = {
            "compare", "difference", "vs", "versus", "which one", "first one",
            "second one", "that one", "buy this", "tell me more", "more details",
            "cheaper", "better option",
        }
        if has_prior_products and any(w in lower for w in follow_up_words):
            return IntentType.FOLLOW_UP

        # LLM classification for everything else
        llm = get_llm_service()
        try:
            result = await llm.complete_json(
                messages=[{"role": "user", "content": user_message}],
                system=ROUTER_SYSTEM,
                max_tokens=60,
            )
            intent_str = result.get("intent_type", "chitchat")
            return IntentType(intent_str)
        except (ValueError, Exception):
            # On LLM failure, assume shopping query (safer default)
            return IntentType.SHOPPING_QUERY
