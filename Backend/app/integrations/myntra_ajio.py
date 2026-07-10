"""
app/integrations/myntra.py  /  ajio.py  (combined file, split at runtime)
──────────────────────────────────────────────────────────────────────────
Myntra and Ajio fashion affiliate integrations (via Admitad / VCommission).

⚠️  These run on affiliate product feeds, not a general search API. Both an
    affiliate token AND your feed URL (from your Admitad/VCommission
    dashboard) are required — there is no public default. Until both are
    set, these integrations stay disabled and are skipped.

ADD_API_HERE: settings.myntra_affiliate_token, settings.myntra_feed_url,
              settings.ajio_affiliate_token, settings.ajio_feed_url
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

# ─────────────────────────────────────────────────────────────────────────────
# Myntra
# ─────────────────────────────────────────────────────────────────────────────

class MyntraIntegration(BaseIntegration):
    platform = Platform.MYNTRA
    platform_type = PlatformType.ECOMMERCE

    def __init__(self) -> None:
        super().__init__()
        self.enabled = (
            settings.myntra_affiliate_token not in ("", _PLACEHOLDER)
            and settings.myntra_feed_url not in ("", _PLACEHOLDER)
        )

    async def search(
        self, intent: SearchIntent, pincode: Optional[str] = None
    ) -> List[Product]:
        """
        ADD API HERE
        Admitad / VCommission feed URL for Myntra, e.g.:
        https://export.admitad.com/en/webmaster/websites/.../feed/
        Set it as MYNTRA_FEED_URL in .env.
        """
        if not self.enabled:
            return []

        url = settings.myntra_feed_url
        headers = {"Authorization": f"Bearer {settings.myntra_affiliate_token}"}
        params = {"q": intent.query_text, "limit": 10}

        try:
            resp = await self._get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        return [self._parse_item(p) for p in data.get("products", [])]

    @staticmethod
    def _parse_item(item: dict) -> Product:
        """ADD API HERE — adapt to actual Myntra/Admitad feed schema."""
        return Product(
            product_id=item.get("id") or str(uuid.uuid4()),
            title=item.get("name", "Myntra Product"),
            platform=Platform.MYNTRA,
            platform_type=PlatformType.ECOMMERCE,
            price=PriceInfo(
                current=float(item.get("price", 0)),
                original=float(item.get("old_price", 0)) or None,
            ),
            image_url=item.get("picture"),
            product_url=item.get("url", "https://myntra.com"),
            affiliate_url=item.get("goto_link"),
            brand=item.get("brand"),
            delivery=DeliveryInfo(estimated_days=4, label="Myntra delivery 4-5 days"),
            review_summary=ReviewSummary(
                average_rating=float(item.get("rating", 0)) or None,
                total_reviews=item.get("num_reviews"),
            ),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Ajio
# ─────────────────────────────────────────────────────────────────────────────

class AjioIntegration(BaseIntegration):
    platform = Platform.AJIO
    platform_type = PlatformType.ECOMMERCE

    def __init__(self) -> None:
        super().__init__()
        self.enabled = (
            settings.ajio_affiliate_token not in ("", _PLACEHOLDER)
            and settings.ajio_feed_url not in ("", _PLACEHOLDER)
        )

    async def search(
        self, intent: SearchIntent, pincode: Optional[str] = None
    ) -> List[Product]:
        """
        ADD API HERE
        Admitad feed URL for Ajio. Set it as AJIO_FEED_URL in .env.
        """
        if not self.enabled:
            return []

        url = settings.ajio_feed_url
        headers = {"Authorization": f"Bearer {settings.ajio_affiliate_token}"}
        params = {"q": intent.query_text, "limit": 10}

        try:
            resp = await self._get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        return [self._parse_item(p) for p in data.get("products", [])]

    @staticmethod
    def _parse_item(item: dict) -> Product:
        """ADD API HERE — adapt to actual Ajio/Admitad feed schema."""
        return Product(
            product_id=item.get("id") or str(uuid.uuid4()),
            title=item.get("name", "Ajio Product"),
            platform=Platform.AJIO,
            platform_type=PlatformType.ECOMMERCE,
            price=PriceInfo(
                current=float(item.get("price", 0)),
                original=float(item.get("old_price", 0)) or None,
            ),
            image_url=item.get("picture"),
            product_url=item.get("url", "https://ajio.com"),
            affiliate_url=item.get("goto_link"),
            brand=item.get("brand"),
            delivery=DeliveryInfo(estimated_days=5, label="Ajio delivery 5-7 days"),
        )
