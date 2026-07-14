"""
app/integrations/quickcommerce.py
─────────────────────────────────
Universal integration using the QuickCommerce API.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

import httpx
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

class QuickCommerceIntegration(BaseIntegration):
    def __init__(
        self,
        qc_platform_name: str,
        platform_enum: Platform,
        platform_type: PlatformType,
    ) -> None:
        super().__init__()
        self.qc_platform_name = qc_platform_name
        self.platform = platform_enum
        self.platform_type = platform_type
        self._http = httpx.AsyncClient(timeout=3.5)
        
        self.enabled = bool(settings.quickcommerce_api_key and settings.quickcommerce_api_key != "ADD_API_HERE")

    async def search(
        self, intent: SearchIntent, pincode: Optional[str] = None
    ) -> List[Product]:
        if not self.enabled:
            return []

        url = f"{settings.quickcommerce_api_base_url}/search"
        headers = {
            "X-API-Key": settings.quickcommerce_api_key,
        }
        
        # Hardcoding Bangalore coordinates if lat/lon is needed for API
        params = {
            "q": intent.query_text,
            "platform": self.qc_platform_name,
            "lat": 12.90,
            "lon": 77.66
        }

        try:
            resp = await self._get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"QuickCommerce API error for {self.qc_platform_name}: {e}")
            return []

        products_data = data.get("data", {}).get("products", [])
        return [self._parse_item(item) for item in products_data]

    def _parse_item(self, item: dict) -> Product:
        # Based on the test log format
        platform_info = item.get("platform", {})
        sla = platform_info.get("sla", "Standard delivery")
        
        is_quick = self.platform_type == PlatformType.QUICK_COMMERCE
        
        # Parse minutes from "8 mins"
        estimated_minutes = None
        if "min" in sla.lower():
            try:
                estimated_minutes = int(sla.lower().split(" min")[0].strip())
            except:
                estimated_minutes = 15
        
        estimated_days = 2 if not is_quick else None
        if "day" in sla.lower():
            try:
                estimated_days = int(sla.lower().split(" day")[0].strip())
            except:
                estimated_days = 2

        image_url = item.get("images", [None])[0] if item.get("images") else None

        return Product(
            product_id=str(item.get("id")) or str(uuid.uuid4()),
            title=item.get("name", "Product"),
            platform=self.platform,
            platform_type=self.platform_type,
            price=PriceInfo(
                current=float(item.get("offer_price", 0)),
                original=float(item.get("mrp", 0)) or None,
            ),
            image_url=image_url,
            product_url=item.get("deeplink") or f"https://{self.qc_platform_name.lower()}.com",
            brand=item.get("brand"),
            in_stock=item.get("available", True),
            delivery=DeliveryInfo(
                estimated_minutes=estimated_minutes,
                estimated_days=estimated_days,
                is_express=is_quick,
                label=sla,
            ),
            review_summary=ReviewSummary(
                average_rating=item.get("rating"),
                total_reviews=item.get("rating_count"),
            ),
        )
