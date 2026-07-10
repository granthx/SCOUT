"""
app/models/intent.py
────────────────────
Structured intent extracted from a natural-language user query.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    SHOPPING_QUERY = "shopping_query"       # "best wireless headphones under ₹3000"
    QUICK_COMMERCE = "quick_commerce"       # "milk and bread, fastest delivery"
    PRICE_CHECK = "price_check"             # "what's the cheapest iPhone right now"
    REVIEW_REQUEST = "review_request"       # "reviews of Sony WH-1000XM5"
    PRICE_ALERT = "price_alert"             # "alert me when price drops below ₹2000"
    FOLLOW_UP = "follow_up"                 # "compare the first two options"
    CHITCHAT = "chitchat"                   # small talk / off-topic


class SortPriority(str, Enum):
    LOWEST_PRICE = "lowest_price"
    BEST_RATING = "best_rating"
    FASTEST_DELIVERY = "fastest_delivery"
    BEST_VALUE = "best_value"               # default composite score


class SearchIntent(BaseModel):
    """
    Structured output from the intent extractor.
    Every field is optional — the extractor fills what it can infer.
    """

    intent_type: IntentType = IntentType.SHOPPING_QUERY
    query_text: str                                  # cleaned search phrase
    category: Optional[str] = None                  # "electronics", "grocery", "fashion"
    subcategory: Optional[str] = None               # "headphones", "smartphones"
    brand: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)

    # Budget
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    currency: str = "INR"

    # User priorities (in order)
    sort_priority: SortPriority = SortPriority.BEST_VALUE
    must_have_features: List[str] = Field(default_factory=list)
    nice_to_have_features: List[str] = Field(default_factory=list)

    # Location
    pincode: Optional[str] = None
    city: Optional[str] = None

    # Quick commerce specifics
    is_urgent: bool = False                          # "fastest", "now", "ASAP"
    quantity: Optional[int] = None

    # Platform hints
    preferred_platforms: List[str] = Field(default_factory=list)
    exclude_platforms: List[str] = Field(default_factory=list)

    # Follow-up context
    refers_to_previous: bool = False
    reference_index: Optional[int] = None           # "the second one" → 1
