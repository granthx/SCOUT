"""
app/integrations/instamart.py
──────────────────────────────
Swiggy Instamart quick-commerce integration.

⚠️  No public self-serve API. Both INSTAMART_API_KEY and
    INSTAMART_API_BASE_URL must come from an approved partner / licensed
    data provider — there is no working default. Until both are set,
    this integration stays disabled and is skipped (other configured
    platforms, e.g. SerpAPI, are unaffected).

ADD_API_HERE: settings.instamart_api_key, settings.instamart_api_base_url
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


class InstamartIntegration(BaseIntegration):
    platform = Platform.INSTAMART
    platform_type = PlatformType.QUICK_COMMERCE

    def __init__(self) -> None:
        super().__init__()
        self.enabled = (
            settings.instamart_api_key not in ("", _PLACEHOLDER)
            and settings.instamart_api_base_url not in ("", _PLACEHOLDER)
        )

    async def search(
        self, intent: SearchIntent, pincode: Optional[str] = None
    ) -> List[Product]:
        """
        ─────────────────────────────────────────────────────────────────────
        ADD API HERE
        ─────────────────────────────────────────────────────────────────────
        url = f"{settings.instamart_api_base_url}/mapi/search"
        headers = {
            "Authorization": f"Bearer {settings.instamart_api_key}",
            "x-delivery-pincode": pincode,
        }
        ─────────────────────────────────────────────────────────────────────
        """
        if not self.enabled:
            return []

        url = f"{settings.instamart_api_base_url}/mapi/search"      # ADD_API_HERE
        headers = {
            "Authorization": f"Bearer {settings.instamart_api_key}", # ADD_API_HERE
            "x-delivery-pincode": pincode or "",
        }
        params = {"searchKey": intent.query_text, "pageNumber": 1, "pageSize": 20}

        try:
            resp = await self._get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        items = data.get("data", {}).get("products", [])
        return [self._parse_item(p) for p in items]

    @staticmethod
    def _parse_item(item: dict) -> Product:
        """ADD API HERE — adapt to actual Instamart response schema."""
        return Product(
            product_id=item.get("productId") or str(uuid.uuid4()),
            title=item.get("productName", "Instamart Product"),
            platform=Platform.INSTAMART,
            platform_type=PlatformType.QUICK_COMMERCE,
            price=PriceInfo(
                current=float(item.get("price", {}).get("value", 0)),
                original=float(item.get("mrp", {}).get("value", 0)) or None,
            ),
            image_url=item.get("imageUrl"),
            product_url=item.get("deepLink", "https://www.swiggy.com/instamart"),
            brand=item.get("brand"),
            in_stock=item.get("available", True),
            delivery=DeliveryInfo(
                estimated_minutes=item.get("deliveryTimeInMins", 15),
                is_express=True,
                label=f"~{item.get('deliveryTimeInMins', 15)} min via Instamart",
            ),
        )
