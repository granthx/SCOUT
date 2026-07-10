"""
app/integrations/blinkit.py
────────────────────────────
Blinkit (quick commerce) integration.

⚠️  Blinkit has NO public API and no affiliate program.
    This module is a ready-to-wire adapter.
    When you obtain API access (via official partnership or a
    licensed data provider), fill in BLINKIT_API_KEY and
    BLINKIT_API_BASE_URL in your .env file.

    Until then, this integration stays disabled and is skipped during
    search — it will NOT block other platforms (e.g. SerpAPI) from working.

ADD_API_HERE:
  - settings.blinkit_api_key
  - settings.blinkit_api_base_url
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

_PLACEHOLDER = "ADD_API_HERE"


class BlinkitIntegration(BaseIntegration):
    platform = Platform.BLINKIT
    platform_type = PlatformType.QUICK_COMMERCE

    def __init__(self) -> None:
        super().__init__()
        # Both the key AND the base URL must be real — there is no working
        # default base URL since Blinkit has no public API.
        self.enabled = (
            settings.blinkit_api_key not in ("", _PLACEHOLDER)
            and settings.blinkit_api_base_url not in ("", _PLACEHOLDER)
        )

    async def search(
        self, intent: SearchIntent, pincode: Optional[str] = None
    ) -> List[Product]:
        """
        ─────────────────────────────────────────────────────────────────────
        Expected API call pattern (replace with real endpoint once you have
        partner / licensed-provider credentials):

            url = f"{settings.blinkit_api_base_url}/v1/products/search"
            headers = {
                "Authorization": f"Bearer {settings.blinkit_api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "query": intent.query_text,
                "latitude": <lat from pincode lookup>,
                "longitude": <lng from pincode lookup>,
                "limit": 20,
            }
            resp = await self._post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return [self._parse_item(item) for item in data.get("products", [])]
        ─────────────────────────────────────────────────────────────────────
        """
        if not self.enabled:
            return []

        # ── REPLACE BELOW with real API call ──────────────────────────────────
        url = f"{settings.blinkit_api_base_url}/v1/products/search"  # ADD_API_HERE
        headers = {
            "Authorization": f"Bearer {settings.blinkit_api_key}",   # ADD_API_HERE
            "X-Pincode": pincode or "",
        }
        params = {"q": intent.query_text, "limit": 20}

        try:
            resp = await self._get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        return [self._parse_item(item) for item in data.get("products", [])]

    @staticmethod
    def _parse_item(item: dict) -> Product:
        """
        ADD_API_HERE — adapt field names to match the actual Blinkit API response.
        """
        return Product(
            product_id=item.get("id") or str(uuid.uuid4()),
            title=item.get("name", "Blinkit Product"),
            platform=Platform.BLINKIT,
            platform_type=PlatformType.QUICK_COMMERCE,
            price=PriceInfo(
                current=float(item.get("selling_price", 0)),
                original=float(item.get("mrp", 0)) or None,
            ),
            image_url=item.get("image_url"),
            product_url=item.get("product_url", "https://blinkit.com"),
            brand=item.get("brand"),
            in_stock=item.get("in_stock", True),
            delivery=DeliveryInfo(
                estimated_minutes=item.get("delivery_time_minutes", 10),
                is_express=True,
                label=f"~{item.get('delivery_time_minutes', 10)} min delivery",
            ),
            review_summary=ReviewSummary(
                average_rating=float(item.get("rating", 0)) or None,
                total_reviews=item.get("review_count"),
            ),
        )
