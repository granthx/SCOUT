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
    def _infer_platform(source: Optional[str]) -> Platform:
        if not source:
            return Platform.SERP
        src_lower = source.lower()
        if "amazon" in src_lower:
            return Platform.AMAZON
        if "flipkart" in src_lower:
            return Platform.FLIPKART
        if "myntra" in src_lower:
            return Platform.MYNTRA
        if "ajio" in src_lower:
            return Platform.AJIO
        if "nykaa" in src_lower:
            return Platform.NYKAA
        if "blinkit" in src_lower:
            return Platform.BLINKIT
        if "zepto" in src_lower:
            return Platform.ZEPTO
        if "instamart" in src_lower or "swiggy" in src_lower:
            return Platform.INSTAMART
        if "zomato" in src_lower:
            return Platform.ZOMATO
        return Platform.SERP

    @staticmethod
    def _generate_fallback_url(source: Optional[str], title: str) -> Optional[str]:
        if not source or not title:
            return None
            
        import urllib.parse
        src_lower = source.lower()
        title_encoded = urllib.parse.quote(title)
        
        # Explicit store search mappings
        if "amazon" in src_lower:
            return f"https://www.amazon.in/s?k={title_encoded}"
        if "flipkart" in src_lower:
            return f"https://www.flipkart.com/search?q={title_encoded}"
        if "ubuy" in src_lower:
            return f"https://www.ubuy.co.in/search/?q={title_encoded}"
        if "reliance" in src_lower:
            return f"https://www.reliancedigital.in/search?q={title_encoded}:relevance"
        if "croma" in src_lower:
            return f"https://www.croma.com/search/?q={title_encoded}:relevance:isStockAvailable:true"
        if "vijay sales" in src_lower:
            return f"https://www.vijaysales.com/search/{title_encoded}"
        if "desertcart" in src_lower:
            return f"https://www.desertcart.in/search/{title_encoded}"
        if "tradeindia" in src_lower:
            return f"https://www.tradeindia.com/search.html?keyword={title_encoded}"
        if "blinkit" in src_lower:
            return f"https://blinkit.com/s/?q={title_encoded}"
        if "zepto" in src_lower:
            return f"https://www.zeptonow.com/search?q={title_encoded}"
        if "instamart" in src_lower or "swiggy" in src_lower:
            return f"https://www.swiggy.com/instamart/search?custom_back=true&query={title_encoded}"
        if "myntra" in src_lower:
            return f"https://www.myntra.com/{title_encoded}"
        if "ajio" in src_lower:
            return f"https://www.ajio.com/search/?text={title_encoded}"
        if "nykaa" in src_lower:
            return f"https://www.nykaa.com/search/result/?q={title_encoded}"
        
        # If the source is just one word or a domain like "ZOZILA.COM" or "SCOFFCO"
        domain = source.strip().lower()
        if " " not in domain:
            if "." not in domain:
                domain += ".com"  # guess .com if missing
            return f"https://{domain}/search?q={title_encoded}"
            
        # Final fallback: A standard Google Search (bypasses Google Shopping overlay)
        source_encoded = urllib.parse.quote(source)
        return f"https://www.google.com/search?q={source_encoded}+{title_encoded}"

    @staticmethod
    def _parse_item(item: dict) -> Product:
        raw_price = item.get("price", "0")
        # SerpAPI returns prices like "₹2,999" or "$29.99"
        price_val = float(
            raw_price.replace("₹", "").replace(",", "").replace("$", "").strip()
            or "0"
        )
        source = item.get("source")
        return Product(
            product_id=item.get("product_id") or str(uuid.uuid4()),
            title=item.get("title", "Unknown Product"),
            platform=SerpAPIIntegration._infer_platform(source),
            platform_type=PlatformType.ECOMMERCE,
            price=PriceInfo(current=price_val),
            image_url=item.get("thumbnail"),
            product_url=item.get("link") or SerpAPIIntegration._generate_fallback_url(source, item.get("title", "")) or item.get("product_link", "#"),
            brand=source,
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
