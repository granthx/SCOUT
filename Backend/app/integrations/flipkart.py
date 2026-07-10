"""
app/integrations/flipkart.py
──────────────────────────────
Flipkart Affiliate API integration.
API docs: https://affiliate.flipkart.com/api-docs

ADD_API_HERE: settings.flipkart_affiliate_id, settings.flipkart_affiliate_token
"""
from __future__ import annotations

import uuid
from typing import List, Optional
from urllib.parse import quote_plus

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

_BASE = "https://affiliate-api.flipkart.net/affiliate/1.0"


class FlipkartIntegration(BaseIntegration):
    platform = Platform.FLIPKART
    platform_type = PlatformType.ECOMMERCE

    def __init__(self) -> None:
        super().__init__()
        _ph = ("", "ADD_API_HERE")
        self.enabled = (
            settings.flipkart_affiliate_id not in _ph
            and settings.flipkart_affiliate_token not in _ph
        )

    async def search(
        self, intent: SearchIntent, pincode: Optional[str] = None
    ) -> List[Product]:
        if not self.enabled:
            return []

        url = f"{_BASE}/product/search"
        headers = {
            "Fk-Affiliate-Id": settings.flipkart_affiliate_id,       # ADD_API_HERE
            "Fk-Affiliate-Token": settings.flipkart_affiliate_token,  # ADD_API_HERE
        }
        params = {
            "query": intent.query_text,
            "resultCount": 10,
        }

        try:
            resp = await self._get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        products = data.get("productInfoList", [])
        return [self._parse_item(p) for p in products]

    @staticmethod
    def _parse_item(item: dict) -> Product:
        pid = item.get("productBaseInfo", {})
        attr = pid.get("productAttributes", {})
        offer = pid.get("productPaymentInfo", {})

        title = attr.get("title", "Flipkart Product")
        brand = attr.get("brand")
        img_url = attr.get("imageUrls", {}).get("400x400")
        fp_url = pid.get("productBaseInfo", {}).get("productUrl", "#")
        aff_url = fp_url  # Flipkart affiliate tracking is in the token header

        selling_price = float(offer.get("sellingPrice", {}).get("amount", 0))
        mrp = float(offer.get("mrp", {}).get("amount", 0))

        rating = float(attr.get("productRating", 0) or 0)
        reviews = int(attr.get("numberOfReviews", 0) or 0)

        return Product(
            product_id=attr.get("productId") or str(uuid.uuid4()),
            title=title,
            platform=Platform.FLIPKART,
            platform_type=PlatformType.ECOMMERCE,
            price=PriceInfo(current=selling_price, original=mrp if mrp else None),
            brand=brand,
            image_url=img_url,
            product_url=fp_url,
            affiliate_url=aff_url,
            delivery=DeliveryInfo(estimated_days=3, label="Flipkart delivery 3-5 days"),
            review_summary=ReviewSummary(
                average_rating=rating or None,
                total_reviews=reviews or None,
            ),
            specs={"highlights": attr.get("highlights", [])},
        )
