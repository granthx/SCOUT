"""
app/integrations/amazon.py
───────────────────────────
Amazon Product Advertising API (PA-API 5.0) integration.
Affiliate feed updated 1-2x daily — legal and structured.
API docs: https://webservices.amazon.com/paapi5/documentation/

ADD_API_HERE: settings.amazon_access_key, settings.amazon_secret_key,
              settings.amazon_partner_tag
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
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

_PAAPI_HOST = "webservices.amazon.in"
_PAAPI_REGION = "eu-west-1"
_PAAPI_ENDPOINT = f"https://{_PAAPI_HOST}/paapi5/searchitems"


class AmazonIntegration(BaseIntegration):
    platform = Platform.AMAZON
    platform_type = PlatformType.ECOMMERCE

    def __init__(self) -> None:
        super().__init__()
        _ph = ("", "ADD_API_HERE")
        self.enabled = (
            settings.amazon_access_key not in _ph
            and settings.amazon_secret_key not in _ph
            and settings.amazon_partner_tag not in _ph
        )

    async def search(
        self, intent: SearchIntent, pincode: Optional[str] = None
    ) -> List[Product]:
        if not self.enabled:
            return []

        payload = self._build_payload(intent)
        headers = self._sign_request(payload)

        try:
            resp = await self._post(
                _PAAPI_ENDPOINT,
                content=json.dumps(payload),
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        items = data.get("SearchResult", {}).get("Items", [])
        return [self._parse_item(item) for item in items]

    # ── Build request ─────────────────────────────────────────────────────────

    def _build_payload(self, intent: SearchIntent) -> dict:
        payload: dict = {
            "Keywords": intent.query_text,
            "PartnerTag": settings.amazon_partner_tag,   # ADD_API_HERE
            "PartnerType": "Associates",
            "Marketplace": "www.amazon.in",
            "Resources": [
                "Images.Primary.Medium",
                "ItemInfo.Title",
                "ItemInfo.ByLineInfo",
                "Offers.Listings.Price",
                "Offers.Listings.DeliveryInfo.IsPrimeEligible",
                "CustomerReviews.StarRating",
                "CustomerReviews.Count",
            ],
            "ItemCount": 10,
        }
        if intent.budget_max:
            payload["MinPrice"] = int(intent.budget_min or 0) * 100   # in paise
            payload["MaxPrice"] = int(intent.budget_max) * 100
        return payload

    # ── AWS SigV4 signing (simplified) ───────────────────────────────────────

    def _sign_request(self, payload: dict) -> dict:
        """
        Full SigV4 implementation.
        ADD_API_HERE: replace with your credentials from settings.
        """
        access_key = settings.amazon_access_key    # ADD_API_HERE
        secret_key = settings.amazon_secret_key    # ADD_API_HERE

        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        body = json.dumps(payload)
        body_hash = hashlib.sha256(body.encode()).hexdigest()

        canonical_headers = (
            f"content-type:application/json; charset=utf-8\n"
            f"host:{_PAAPI_HOST}\n"
            f"x-amz-date:{amz_date}\n"
            f"x-amz-target:com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems\n"
        )
        signed_headers = "content-type;host;x-amz-date;x-amz-target"
        canonical_request = "\n".join([
            "POST", "/paapi5/searchitems", "",
            canonical_headers, signed_headers, body_hash,
        ])

        credential_scope = f"{date_stamp}/{_PAAPI_REGION}/ProductAdvertisingAPI/aws4_request"
        string_to_sign = "\n".join([
            "AWS4-HMAC-SHA256", amz_date, credential_scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ])

        def _hmac(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        signing_key = _hmac(
            _hmac(
                _hmac(
                    _hmac(f"AWS4{secret_key}".encode(), date_stamp),
                    _PAAPI_REGION,
                ),
                "ProductAdvertisingAPI",
            ),
            "aws4_request",
        )
        signature = hmac.new(
            signing_key, string_to_sign.encode(), hashlib.sha256
        ).hexdigest()

        auth_header = (
            f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        return {
            "Content-Type": "application/json; charset=utf-8",
            "X-Amz-Date": amz_date,
            "X-Amz-Target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems",
            "Authorization": auth_header,
        }

    # ── Parse response ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_item(item: dict) -> Product:
        detail_url = item.get("DetailPageURL", "#")
        asin = item.get("ASIN", str(uuid.uuid4()))

        # Price
        listing = (
            item.get("Offers", {})
                .get("Listings", [{}])[0]
        )
        price_val = float(
            listing.get("Price", {}).get("Amount", 0)
        )
        is_prime = listing.get("DeliveryInfo", {}).get("IsPrimeEligible", False)

        # Rating
        cr = item.get("CustomerReviews", {})
        rating = cr.get("StarRating", {}).get("Value")
        count = cr.get("Count")

        # Title / brand
        info = item.get("ItemInfo", {})
        title = info.get("Title", {}).get("DisplayValue", "Amazon Product")
        brand = (
            info.get("ByLineInfo", {})
                .get("Brand", {})
                .get("DisplayValue")
        )

        # Image
        img = (
            item.get("Images", {})
                .get("Primary", {})
                .get("Medium", {})
                .get("URL")
        )

        affiliate_url = (
            f"{detail_url}?tag={settings.amazon_partner_tag}"
            if detail_url != "#" else "#"
        )

        return Product(
            product_id=asin,
            title=title,
            platform=Platform.AMAZON,
            platform_type=PlatformType.ECOMMERCE,
            price=PriceInfo(current=price_val),
            brand=brand,
            image_url=img,
            product_url=detail_url,
            affiliate_url=affiliate_url,
            delivery=DeliveryInfo(
                estimated_days=1 if is_prime else 3,
                is_express=is_prime,
                label="Prime delivery" if is_prime else "Standard 3-5 days",
            ),
            review_summary=ReviewSummary(
                average_rating=float(rating) if rating else None,
                total_reviews=count,
            ),
        )
