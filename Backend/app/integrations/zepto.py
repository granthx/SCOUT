"""
app/integrations/zepto.py
──────────────────────────
Zepto quick-commerce integration.

⚠️  Zepto has no public self-serve API. Both ZEPTO_API_KEY and
    ZEPTO_API_BASE_URL must come from an approved partner / licensed
    data provider — there is no working default. Until both are set,
    this integration stays disabled and is skipped (other configured
    platforms, e.g. SerpAPI, are unaffected).

ADD_API_HERE: settings.zepto_api_key, settings.zepto_api_base_url
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from app.config import get_settings
from app.integrations.base import BaseIntegration
from app.models.intent import SearchIntent
from app.models.product import (
    DeliveryInfo, Platform, PlatformType, PriceInfo, Product, ReviewSummary,
)

settings = get_settings()
_PLACEHOLDER = "ADD_API_HERE"


class ZeptoIntegration(BaseIntegration):
    platform = Platform.ZEPTO
    platform_type = PlatformType.QUICK_COMMERCE

    def __init__(self) -> None:
        super().__init__()
        self.enabled = (
            settings.zepto_api_key not in ("", _PLACEHOLDER)
            and settings.zepto_api_base_url not in ("", _PLACEHOLDER)
        )

    async def search(
        self, intent: SearchIntent, pincode: Optional[str] = None
    ) -> List[Product]:
        """
        ─────────────────────────────────────────────────────────────────────
        ADD API HERE
        ─────────────────────────────────────────────────────────────────────
        url = f"{settings.zepto_api_base_url}/api/v2/search"
        headers = {"x-api-key": settings.zepto_api_key, "x-pincode": pincode}
        payload = {"query": intent.query_text, "page_size": 20}
        ─────────────────────────────────────────────────────────────────────
        """
        if not self.enabled:
            return []

        url = f"{settings.zepto_api_base_url}/api/v2/search"   # ADD_API_HERE
        headers = {
            "x-api-key": settings.zepto_api_key,               # ADD_API_HERE
            "x-pincode": pincode or "",
        }
        params = {"query": intent.query_text, "page_size": 20}

        try:
            resp = await self._get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        return [self._parse_item(p) for p in data.get("results", [])]

    @staticmethod
    def _parse_item(item: dict) -> Product:
        """ADD API HERE — adapt to actual Zepto response schema."""
        return Product(
            product_id=item.get("product_id") or str(uuid.uuid4()),
            title=item.get("product_name", "Zepto Product"),
            platform=Platform.ZEPTO,
            platform_type=PlatformType.QUICK_COMMERCE,
            price=PriceInfo(
                current=float(item.get("discounted_price", 0)),
                original=float(item.get("mrp", 0)) or None,
            ),
            image_url=item.get("image_url"),
            product_url=item.get("deep_link", "https://zepto.co"),
            brand=item.get("brand"),
            in_stock=not item.get("out_of_stock", False),
            delivery=DeliveryInfo(
                estimated_minutes=item.get("eta_minutes", 10),
                is_express=True,
                label=f"~{item.get('eta_minutes', 10)} min delivery",
            ),
            review_summary=ReviewSummary(
                average_rating=float(item.get("rating", 0)) or None,
            ),
        )
