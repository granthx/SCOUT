"""
app/tools/review_summarizer.py
───────────────────────────────
Uses Claude to extract pros, cons, and a one-sentence verdict from raw reviews.
Runs concurrently for the top N products to stay within latency budget.
"""
from __future__ import annotations

import asyncio
import json
from typing import List

from app.agent.prompts import REVIEW_SUMMARISER_SYSTEM
from app.models.product import Product, ReviewSummary
from app.services.llm_service import get_llm_service

_MAX_REVIEW_CHARS = 3_000      # truncate per-product to stay within token budget
_TOP_N_TO_SUMMARISE = 5        # only summarise top-N ranked products


class ReviewSummarizer:
    """Adds LLM-generated pros/cons/summary to each product's review_summary."""

    async def enrich(self, products: List[Product]) -> List[Product]:
        """
        Enrich the top-N products with AI review summaries.
        Products outside top-N keep whatever data came from the platform API.
        """
        targets = [p for p in products[:_TOP_N_TO_SUMMARISE] if p.raw_reviews]
        if not targets:
            return products

        tasks = [asyncio.create_task(self._summarise_one(p)) for p in targets]
        await asyncio.gather(*tasks, return_exceptions=True)
        return products

    async def _summarise_one(self, product: Product) -> None:
        llm = get_llm_service()
        review_text = "\n".join(product.raw_reviews)[:_MAX_REVIEW_CHARS]

        user_content = (
            f"Product: {product.title}\n"
            f"Platform: {product.platform.value}\n"
            f"Price: ₹{product.price.current:,.0f}\n\n"
            f"Customer Reviews:\n{review_text}"
        )

        try:
            raw = await llm.complete_json(
                messages=[{"role": "user", "content": user_content}],
                system=REVIEW_SUMMARISER_SYSTEM,
                max_tokens=400,
            )
            rs = product.review_summary or ReviewSummary()
            rs.summary = raw.get("summary")
            rs.pros = raw.get("pros", [])
            rs.cons = raw.get("cons", [])
            product.review_summary = rs
        except Exception:
            # Summarisation is best-effort; never block the main flow
            pass
