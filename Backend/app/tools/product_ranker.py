"""
app/tools/product_ranker.py
────────────────────────────
Multi-factor product scoring and ranking engine.

Score breakdown (weights sum to 1.0):
  price_fit       0.30  — how well price matches budget (1.0 = exact budget match)
  rating          0.25  — normalised star rating
  delivery_speed  0.20  — faster = higher; quick commerce gets bonus
  review_count    0.10  — social proof (log-scaled)
  discount        0.10  — percentage saving vs MRP
  stock           0.05  — in-stock bonus

Weights shift if the user's sort_priority is not best_value:
  lowest_price    → price_fit:0.60, others halved
  best_rating     → rating:0.60, others halved
  fastest_delivery→ delivery_speed:0.60, others halved
"""
from __future__ import annotations

import math
from typing import List

from app.models.intent import SearchIntent, SortPriority
from app.models.product import Product, Platform


_BASE_WEIGHTS = {
    "price_fit": 0.25,
    "rating": 0.20,
    "delivery_speed": 0.15,
    "review_count": 0.10,
    "discount": 0.10,
    "stock": 0.05,
    "platform_priority": 0.15,
}

_PRIORITY_OVERRIDES: dict[SortPriority, dict] = {
    SortPriority.LOWEST_PRICE: {
        "price_fit": 0.50, "rating": 0.13, "delivery_speed": 0.10,
        "review_count": 0.07, "discount": 0.07, "stock": 0.03, "platform_priority": 0.10,
    },
    SortPriority.BEST_RATING: {
        "price_fit": 0.15, "rating": 0.50, "delivery_speed": 0.10,
        "review_count": 0.07, "discount": 0.05, "stock": 0.03, "platform_priority": 0.10,
    },
    SortPriority.FASTEST_DELIVERY: {
        "price_fit": 0.15, "rating": 0.10, "delivery_speed": 0.50,
        "review_count": 0.05, "discount": 0.05, "stock": 0.05, "platform_priority": 0.10,
    },
    SortPriority.BEST_VALUE: _BASE_WEIGHTS,
}


class ProductRanker:
    """Stateless — call rank() on any list of products."""

    def rank(self, products: List[Product], intent: SearchIntent) -> List[Product]:
        if not products:
            return []

        weights = _PRIORITY_OVERRIDES.get(intent.sort_priority, _BASE_WEIGHTS)
        budget_max = intent.budget_max or self._infer_budget(products)
        budget_min = intent.budget_min or 0.0

        for product in products:
            score, breakdown = self._score(product, budget_min, budget_max, weights)
            product.score = round(score * 100, 1)
            product.score_breakdown = {k: round(v, 3) for k, v in breakdown.items()}

        ranked = sorted(products, key=lambda p: p.score or 0, reverse=True)

        # Mark the top pick
        if ranked:
            ranked[0].recommendation_reason = self._pick_reason(ranked[0], intent)

        return ranked

    # ── Scoring ───────────────────────────────────────────────────────────────

    @staticmethod
    def _score(
        product: Product,
        budget_min: float,
        budget_max: float,
        weights: dict,
    ) -> tuple[float, dict]:
        price = product.price.current
        rs = product.review_summary

        # 1. Price fit (0→1): inside budget = 1.0, over budget penalised
        if budget_max > 0:
            if price <= budget_max:
                price_fit = 1.0 - max(0, (price - budget_min) / max(budget_max - budget_min, 1)) * 0.2
            else:
                over_pct = (price - budget_max) / budget_max
                price_fit = max(0.0, 1.0 - over_pct * 2)
        else:
            price_fit = 0.5   # no budget specified — neutral

        # 2. Rating (0→1): 5-star scale normalised
        rating = (rs.average_rating or 0) if rs else 0
        rating_score = rating / 5.0

        # 3. Delivery speed (0→1): minutes or days normalised
        d = product.delivery
        if d.estimated_minutes is not None:
            # Quick commerce: 10 min=1.0, 60 min=0.3
            delivery_score = max(0.0, 1.0 - (d.estimated_minutes - 10) / 100)
        elif d.estimated_days is not None:
            # E-commerce: 1 day=1.0, 7 days=0.0
            delivery_score = max(0.0, 1.0 - (d.estimated_days - 1) / 7)
        else:
            delivery_score = 0.3

        # 4. Review count — log-scaled social proof (0→1 capped at 10 000 reviews)
        review_count = (rs.total_reviews or 0) if rs else 0
        review_score = min(1.0, math.log1p(review_count) / math.log1p(10_000))

        # 5. Discount percentage (0→1)
        discount_pct = product.price.discount_pct or 0.0
        discount_score = min(1.0, discount_pct / 50.0)   # 50% discount = 1.0

        # 6. Stock bonus
        stock_score = 1.0 if product.in_stock else 0.0

        # 7. Platform priority
        platform_name = product.platform.value.lower()
        if product.platform == Platform.SERP and product.brand:
            platform_name = product.brand.lower()
            
        priority_map = {
            "amazon": 1.0,
            "blinkit": 0.9,
            "instamart": 0.8,
            "swiggy": 0.8,
            "zepto": 0.7,
            "flipkart": 0.6,
            "croma": 0.5,
            "chroma": 0.5,
            "vijay sales": 0.4,
            "reliance": 0.3,
            "myntra": 0.2,
        }
        
        platform_score = 0.1
        for k, v in priority_map.items():
            if k in platform_name:
                platform_score = v
                break

        breakdown = {
            "price_fit": price_fit,
            "rating": rating_score,
            "delivery_speed": delivery_score,
            "review_count": review_score,
            "discount": discount_score,
            "stock": stock_score,
            "platform_priority": platform_score,
        }

        total = sum(breakdown[k] * weights[k] for k in breakdown)
        return total, breakdown

    @staticmethod
    def _infer_budget(products: List[Product]) -> float:
        """If no budget specified, use 90th-percentile price as upper bound."""
        prices = sorted(p.price.current for p in products)
        idx = int(len(prices) * 0.9)
        return prices[min(idx, len(prices) - 1)] if prices else 10_000.0

    @staticmethod
    def _pick_reason(product: Product, intent: SearchIntent) -> str:
        parts = []
        price_str = f"₹{product.price.current:,.0f}"
        rs = product.review_summary

        rating_str = (
            f"{rs.average_rating}/5 ({rs.total_reviews:,} reviews)"
            if rs and rs.average_rating and rs.total_reviews
            else ""
        )

        if intent.sort_priority == SortPriority.LOWEST_PRICE:
            parts.append(f"Cheapest option at {price_str}")
        elif intent.sort_priority == SortPriority.BEST_RATING and rating_str:
            parts.append(f"Highest rated at {rating_str}")
        elif intent.sort_priority == SortPriority.FASTEST_DELIVERY:
            parts.append(f"Fastest delivery: {product.delivery.label}")
        else:
            parts.append(f"Best overall value at {price_str}")
            if rating_str:
                parts.append(f"rated {rating_str}")

        if product.price.discount_pct and product.price.discount_pct > 10:
            parts.append(f"{product.price.discount_pct:.0f}% off MRP")

        return " · ".join(parts)
