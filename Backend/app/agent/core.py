"""
app/agent/core.py
──────────────────
CommerceAgent — the central brain of the Universal Commerce Agent.

Orchestration flow per user message:
  1.  Route   → IntentRouter  → IntentType
  2a. Extract → IntentExtractor → SearchIntent         (if shopping/quick/price)
  2b. Direct  → LLM chitchat or follow-up handler      (if chitchat/follow-up)
  3.  Search  → ProductSearchTool → List[Product]      (parallel multi-platform)
  4.  Rank    → ProductRanker → sorted List[Product]
  5.  Enrich  → ReviewSummarizer → pros/cons per product
  6.  Analyse → PriceAnalyzer → price comparison text  (if price_check)
  7.  Stream  → LLM narration + yield ProductCards to frontend

Every step yields SSE StreamChunk events so the frontend can render
progressively (status messages → products → AI narration).
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Optional

from app.agent.prompts import (
    AGENT_SYSTEM,
    CHITCHAT_SYSTEM,
    FOLLOW_UP_SYSTEM,
    RANKER_SYSTEM,
)
from app.agent.router import IntentRouter
from app.models.intent import IntentType, SearchIntent
from app.models.product import ProductCard
from app.models.response import ChunkType, StreamChunk
from app.models.session import Session
from app.services.llm_service import get_llm_service
from app.tools.intent_extractor import IntentExtractor
from app.tools.price_analyzer import PriceAnalyzer
from app.tools.product_ranker import ProductRanker
from app.tools.product_search import ProductSearchTool
from app.tools.review_summarizer import ReviewSummarizer


class CommerceAgent:
    """
    Stateless orchestrator — all state is in the Session object passed in.
    Instantiate once at app startup; call handle() per request.
    """

    def __init__(self) -> None:
        self._router = IntentRouter()
        self._extractor = IntentExtractor()
        self._searcher = ProductSearchTool()
        self._ranker = ProductRanker()
        self._summarizer = ReviewSummarizer()
        self._price_analyzer = PriceAnalyzer()

    # ── Public API ────────────────────────────────────────────────────────────

    async def handle(
        self,
        message: str,
        session: Session,
        pincode: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Async generator that yields StreamChunk objects.
        The SSE route handler serialises these as server-sent events.
        """
        # Update session location hint if provided
        if pincode:
            session.context.user_pincode = pincode

        # ── Step 1: Route ──────────────────────────────────────────────────
        has_prior = bool(session.context.last_products_shown)
        intent_type = await self._router.route(message, has_prior_products=has_prior)

        # ── Step 2: Dispatch ───────────────────────────────────────────────
        if intent_type == IntentType.CHITCHAT:
            async for chunk in self._handle_chitchat(message, session):
                yield chunk

        elif intent_type == IntentType.FOLLOW_UP:
            async for chunk in self._handle_follow_up(message, session):
                yield chunk

        elif intent_type == IntentType.PRICE_CHECK:
            async for chunk in self._handle_price_check(message, session, pincode):
                yield chunk

        else:
            # shopping_query, quick_commerce, review_request
            async for chunk in self._handle_shopping(message, session, intent_type, pincode):
                yield chunk

        yield StreamChunk(type=ChunkType.DONE, session_id=session.session_id)

    # ── Intent handlers ───────────────────────────────────────────────────────

    async def _handle_shopping(
        self,
        message: str,
        session: Session,
        intent_type: IntentType,
        pincode: Optional[str],
    ) -> AsyncIterator[StreamChunk]:
        llm = get_llm_service()

        # Status: let the frontend show a loading indicator
        yield StreamChunk(
            type=ChunkType.THINKING,
            data={"message": "Understanding your query…"},
        )

        # Step 2a: Extract structured intent
        context_summary = self._session_context_text(session)
        try:
            intent: SearchIntent = await self._extractor.extract(message, context_summary)
            intent.intent_type = intent_type
        except Exception:
            intent = SearchIntent(query_text=message, intent_type=intent_type)

        # Apply pincode
        if pincode:
            intent.pincode = pincode
        elif session.context.user_pincode:
            intent.pincode = session.context.user_pincode

        # Echo extracted intent to frontend (useful for debugging / UX)
        yield StreamChunk(type=ChunkType.INTENT, data=intent.model_dump())

        # Step 3: Search
        yield StreamChunk(
            type=ChunkType.THINKING,
            data={"message": f"Searching across platforms for '{intent.query_text}'…"},
        )
        products, platforms_searched = await self._searcher.search(
            intent, pincode=intent.pincode, intent_type=intent_type
        )

        if not products:
            if not self._searcher.has_any_enabled_platform():
                async for chunk in self._stream_text(
                   "I can't search any shopping platforms yet because no shopping "
                   "platforms are enabled. Make sure SERP_API_KEY is configured in "
                   "the .env file and restart the server. Check /api/health to "
                   "see which platforms are active.",
                    session,
                    message,
                ):
                    yield chunk
                return
            async for chunk in self._stream_text(
                f"I couldn't find any results for '{intent.query_text}'. "
                "Try rephrasing, adjusting your budget, or checking the spelling.",
                session,
                message,
            ):
                yield chunk
            return

        # Step 4: Rank
        ranked = self._ranker.rank(products, intent)

        # Step 5: Enrich reviews (best-effort, concurrent)
        await self._summarizer.enrich(ranked)

        # Step 6: Emit product cards to frontend
        cards = [ProductCard.from_product(p) for p in ranked[:8]]
        yield StreamChunk(
            type=ChunkType.PRODUCTS,
            data={
                "products": [c.model_dump() for c in cards],
                "platforms_searched": platforms_searched,
                "total_found": len(products),
            },
        )

        # Update session context so follow-ups work
        session.context.last_products_shown = [c.model_dump() for c in cards]
        session.context.last_search_query = message
        session.context.last_intent_type = intent_type.value
        session.context.last_category = intent.category

        # Step 7: Stream AI narration
        best = ranked[0]
        alt = ranked[1] if len(ranked) > 1 else None

        narration_prompt = (
            f"User asked: {message}\n\n"
            f"Top recommendation:\n"
            f"  Title: {best.title}\n"
            f"  Platform: {best.platform.value}\n"
            f"  Price: ₹{best.price.current:,.0f}\n"
            f"  Rating: {best.review_summary.average_rating if best.review_summary else 'N/A'}/5\n"
            f"  Delivery: {best.delivery.label}\n"
            f"  Why top: {best.recommendation_reason or ''}\n"
        )
        if alt:
            narration_prompt += (
                f"\nAlternative:\n"
                f"  Title: {alt.title}\n"
                f"  Platform: {alt.platform.value}\n"
                f"  Price: ₹{alt.price.current:,.0f}\n"
            )
        narration_prompt += (
            f"\nPlatforms searched: {', '.join(platforms_searched)}\n"
            f"Write a concise 2-3 sentence recommendation."
        )

        history = session.get_history_for_llm()
        history.append({"role": "user", "content": message})

        async for token in llm.stream(
            messages=[{"role": "user", "content": narration_prompt}],
            system=RANKER_SYSTEM,
            max_tokens=300,
        ):
            yield StreamChunk(type=ChunkType.TEXT, data=token)

        session.add_message("user", message)
        session.add_message(
            "assistant",
            f"[Showed {len(cards)} products for: {intent.query_text}]",
        )

    async def _handle_chitchat(
        self, message: str, session: Session
    ) -> AsyncIterator[StreamChunk]:
        llm = get_llm_service()
        history = session.get_history_for_llm()
        history.append({"role": "user", "content": message})

        async for token in llm.stream(
            messages=history,
            system=CHITCHAT_SYSTEM,
            max_tokens=300,
        ):
            yield StreamChunk(type=ChunkType.TEXT, data=token)

        session.add_message("user", message)

    async def _handle_follow_up(
        self, message: str, session: Session
    ) -> AsyncIterator[StreamChunk]:
        llm = get_llm_service()
        prior_products = json.dumps(
            session.context.last_products_shown[:5], indent=2
        )
        history = session.get_history_for_llm()
        history.append({
            "role": "user",
            "content": (
                f"Previously shown products:\n{prior_products}\n\n"
                f"User follow-up: {message}"
            ),
        })

        async for token in llm.stream(
            messages=history,
            system=FOLLOW_UP_SYSTEM,
            max_tokens=400,
        ):
            yield StreamChunk(type=ChunkType.TEXT, data=token)

        session.add_message("user", message)

    async def _handle_price_check(
        self, message: str, session: Session, pincode: Optional[str]
    ) -> AsyncIterator[StreamChunk]:
        intent = await self._extractor.extract(message)
        products, platforms = await self._searcher.search(intent, pincode=pincode)

        if not products:
            if not self._searcher.has_any_enabled_platform():
                async for chunk in self._stream_text(
                    "I can't check prices yet because no API keys are configured. "
                    "Add at least a SERP_API_KEY to the .env file and restart.",
                    session,
                    message,
                ):
                    yield chunk
                return
            async for chunk in self._stream_text(
                "I couldn't find price data for that product right now.", session, message
            ):
                yield chunk
            return

        cheapest, analysis = await self._price_analyzer.analyse(products, message)

        if products:
            cards = [ProductCard.from_product(p) for p in products[:6]]
            yield StreamChunk(
                type=ChunkType.PRODUCTS,
                data={
                    "products": [c.model_dump() for c in cards],
                    "platforms_searched": platforms,
                    "total_found": len(products),
                },
            )

        for token in analysis.split():
            yield StreamChunk(type=ChunkType.TEXT, data=token + " ")
            await asyncio.sleep(0)   # yield control to event loop

        session.add_message("user", message)
        session.add_message("assistant", analysis)

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    async def _stream_text(
        text: str, session: Session, user_message: str
    ) -> AsyncIterator[StreamChunk]:
        for word in text.split():
            yield StreamChunk(type=ChunkType.TEXT, data=word + " ")
            await asyncio.sleep(0)
        session.add_message("user", user_message)
        session.add_message("assistant", text)

    @staticmethod
    def _session_context_text(session: Session) -> str:
        ctx = session.context
        parts = []
        if ctx.last_search_query:
            parts.append(f"Previous search: {ctx.last_search_query}")
        if ctx.last_category:
            parts.append(f"Category: {ctx.last_category}")
        if ctx.user_pincode:
            parts.append(f"User pincode: {ctx.user_pincode}")
        return " | ".join(parts)


# ── Module-level singleton ────────────────────────────────────────────────────

_agent: Optional[CommerceAgent] = None


def get_commerce_agent() -> CommerceAgent:
    global _agent
    if _agent is None:
        _agent = CommerceAgent()
    return _agent
