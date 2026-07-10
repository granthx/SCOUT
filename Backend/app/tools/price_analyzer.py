"""
app/tools/price_analyzer.py
────────────────────────────
Cross-platform price comparison and analysis.
Compares prices for the same product across all platforms,
identifies the best deal, and generates a plain-text analysis.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.agent.prompts import PRICE_ANALYSIS_SYSTEM
from app.models.product import Product
from app.services.llm_service import get_llm_service


class PriceAnalyzer:

    async def analyse(
        self,
        products: List[Product],
        query: str,
    ) -> Tuple[Optional[Product], str]:
        """
        Returns (cheapest_product, analysis_text).
        analysis_text is an LLM-generated 2-3 sentence summary.
        """
        if not products:
            return None, "No products found to compare."

        # Build price table
        price_table = self._build_table(products)
        cheapest = min(products, key=lambda p: p.price.current)

        llm = get_llm_service()
        user_content = (
            f"Product search: {query}\n\n"
            f"Price comparison across platforms:\n{price_table}"
        )

        try:
            analysis = await llm.complete(
                messages=[{"role": "user", "content": user_content}],
                system=PRICE_ANALYSIS_SYSTEM,
                max_tokens=200,
                temperature=0.1,
            )
        except Exception:
            # Fallback to a simple template if LLM fails
            analysis = (
                f"Best price: ₹{cheapest.price.current:,.0f} on "
                f"{cheapest.platform.value.title()}. "
                f"Prices range from ₹{min(p.price.current for p in products):,.0f} "
                f"to ₹{max(p.price.current for p in products):,.0f} across platforms."
            )

        return cheapest, analysis

    @staticmethod
    def _build_table(products: List[Product]) -> str:
        rows = []
        for p in sorted(products, key=lambda x: x.price.current):
            discount = (
                f" ({p.price.discount_pct:.0f}% off)"
                if p.price.discount_pct and p.price.discount_pct > 0
                else ""
            )
            rows.append(
                f"  {p.platform.value.title():12s} ₹{p.price.current:>8,.0f}{discount}"
            )
        return "\n".join(rows)

    @staticmethod
    def platform_price_map(products: List[Product]) -> Dict[str, float]:
        return {p.platform.value: p.price.current for p in products}
