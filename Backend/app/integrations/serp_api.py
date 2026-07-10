"""
app/integrations/serp_api.py
─────────────────────────────
SerpAPI Google Shopping integration.
This is the primary, legally clean data source for e-commerce search.
API docs: https://serpapi.com/google-shopping-api

407a9fd1c40844d546de5b013ecca722191edc2e5d4732e271e28c0e2a048266: settings.serp_api_key
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from app.config import get_settings
from app.integrations.base import BaseIntegration
from app.models.intent import SearchIntent
from app.models.product import (
    DeliveryInfo,
    Platform,
    PlatformType,
    PriceInfo,
    Product,
    ReviewSummary,
)

settings = get_settings()


class SerpAPIIntegration(BaseIntegration):
    platform = Platform.SERP
    platform_type = PlatformType.ECOMMERCE

    def __init__(self) -> None:
        super().__init__()

        print("=" * 50)
        print("SERP KEY:", settings.serp_api_key)
        print("=" * 50)

        self.enabled = bool(settings.serp_api_key)

        print("SERP ENABLED:", self.enabled)

    async def search(
        self, intent: SearchIntent, pincode: Optional[str] = None
    ) -> List[Product]:
        if not self.enabled:
            return []

        params = {
            "engine": "google_shopping",
            "q": self._build_query(intent),
            "api_key": settings.serp_api_key,   # ADD_API_HERE
            "gl": "in",                           # India
            "hl": "en",
            "num": 20,
        }
        if intent.budget_max:
            params["price_max"] = int(intent.budget_max)
        if intent.budget_min:
            params["price_min"] = int(intent.budget_min)

        try:
            resp = await self._get(settings.serp_api_base_url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        return [
            self._parse_item(item)
            for item in data.get("shopping_results", [])
            if item.get("price")
        ]

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_query(intent: SearchIntent) -> str:
        parts = [intent.query_text]
        if intent.brand and intent.brand.lower() not in intent.query_text.lower():
            parts.insert(0, intent.brand)
        return " ".join(parts)

    @staticmethod
    def _parse_item(item: dict) -> Product:
        raw_price = item.get("price", "0")
        # SerpAPI returns prices like "₹2,999" or "$29.99"
        price_val = float(
            raw_price.replace("₹", "").replace(",", "").replace("$", "").strip()
            or "0"
        )
        return Product(
            product_id=item.get("product_id") or str(uuid.uuid4()),
            title=item.get("title", "Unknown Product"),
            platform=Platform.SERP,
            platform_type=PlatformType.ECOMMERCE,
            price=PriceInfo(current=price_val),
            image_url=item.get("thumbnail"),
            product_url=item.get("link", "#"),
            brand=item.get("source"),
            review_summary=ReviewSummary(
                average_rating=float(item["rating"]) if item.get("rating") else None,
                total_reviews=item.get("reviews"),
            ),
            delivery=DeliveryInfo(
                estimated_days=3,
                label=item.get("delivery") or "Standard delivery",
            ),
            specs={"snippet": item.get("snippet", "")},
        )
