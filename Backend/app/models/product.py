"""
app/models/product.py
─────────────────────
Canonical data shapes for products across all platforms.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class Platform(str, Enum):
    AMAZON = "amazon"
    FLIPKART = "flipkart"
    MYNTRA = "myntra"
    AJIO = "ajio"
    NYKAA = "nykaa"
    BLINKIT = "blinkit"
    ZEPTO = "zepto"
    INSTAMART = "instamart"
    ZOMATO = "zomato"
    CHROMA = "chroma"
    CROMA = "croma"
    VIJAY_SALES = "vijay sales"
    RELIANCE = "reliance"
    SERP = "serp"              # fallback when source is Google Shopping


class PlatformType(str, Enum):
    ECOMMERCE = "ecommerce"
    QUICK_COMMERCE = "quick_commerce"


class DeliveryInfo(BaseModel):
    estimated_minutes: Optional[int] = None       # for quick commerce
    estimated_days: Optional[int] = None          # for e-commerce
    is_express: bool = False
    label: str = "Standard delivery"             # human-readable string


class PriceInfo(BaseModel):
    current: float
    original: Optional[float] = None             # MRP / strike-through price
    currency: str = "INR"
    discount_pct: Optional[float] = None

    def model_post_init(self, __context: Any) -> None:
        if self.original and self.original > self.current:
            self.discount_pct = round(
                (self.original - self.current) / self.original * 100, 1
            )


class ReviewSummary(BaseModel):
    average_rating: Optional[float] = None
    total_reviews: Optional[int] = None
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    summary: Optional[str] = None                # LLM-generated one-liner


class Product(BaseModel):
    """Unified product model — platform-agnostic."""

    product_id: str
    title: str
    platform: Platform
    platform_type: PlatformType
    price: PriceInfo
    delivery: DeliveryInfo = Field(default_factory=DeliveryInfo)
    image_url: Optional[str] = None
    product_url: str
    affiliate_url: Optional[str] = None          # tracked affiliate link
    brand: Optional[str] = None
    category: Optional[str] = None
    specs: Dict[str, Any] = Field(default_factory=dict)
    in_stock: bool = True
    review_summary: Optional[ReviewSummary] = None
    raw_reviews: List[str] = Field(default_factory=list)  # fed to summariser

    # Set by the ranker — not from platform API
    score: Optional[float] = None
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    recommendation_reason: Optional[str] = None


class ProductCard(BaseModel):
    """Slim version sent to the frontend."""

    product_id: str
    title: str
    platform: str
    price_display: str
    original_price_display: Optional[str] = None
    discount_pct: Optional[float] = None
    rating: Optional[float] = None
    total_reviews: Optional[int] = None
    delivery_label: str
    image_url: Optional[str] = None
    affiliate_url: Optional[str] = None
    product_url: str
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    review_summary: Optional[str] = None
    score: Optional[float] = None
    recommendation_reason: Optional[str] = None
    in_stock: bool = True

    @classmethod
    def from_product(cls, p: Product) -> "ProductCard":
        rs = p.review_summary
        price_display = f"₹{p.price.current:,.0f}"
        orig_display = (
            f"₹{p.price.original:,.0f}" if p.price.original else None
        )
        
        display_platform = p.platform.value
        if p.platform == Platform.SERP and p.brand:
            display_platform = p.brand

        return cls(
            product_id=p.product_id,
            title=p.title,
            platform=display_platform,
            price_display=price_display,
            original_price_display=orig_display,
            discount_pct=p.price.discount_pct,
            rating=rs.average_rating if rs else None,
            total_reviews=rs.total_reviews if rs else None,
            delivery_label=p.delivery.label,
            image_url=p.image_url,
            affiliate_url=p.affiliate_url or p.product_url,
            product_url=p.product_url,
            pros=rs.pros if rs else [],
            cons=rs.cons if rs else [],
            review_summary=rs.summary if rs else None,
            score=p.score,
            recommendation_reason=p.recommendation_reason,
            in_stock=p.in_stock,
        )
