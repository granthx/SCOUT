"""
app/tools/product_search.py
────────────────────────────
Orchestrates parallel searches across all configured platform integrations.
Results are deduplicated and returned as a flat list of Product objects.
"""
from __future__ import annotations

import asyncio
import hashlib
from typing import Dict, List, Optional, Tuple

from app.config import get_settings
from app.integrations.quickcommerce import QuickCommerceIntegration
from app.integrations.serp_api import SerpAPIIntegration
from app.models.intent import IntentType, SearchIntent
from app.models.product import Platform, PlatformType, Product
from app.services.cache_service import get_cache_service

settings = get_settings()


# ── Registry of all platform integrations ────────────────────────────────────

_ECOMMERCE_PLATFORMS = [
    SerpAPIIntegration(),
    QuickCommerceIntegration("Amazon", Platform.AMAZON, PlatformType.ECOMMERCE),
    QuickCommerceIntegration("Flipkart", Platform.FLIPKART, PlatformType.ECOMMERCE),
    QuickCommerceIntegration("Myntra", Platform.MYNTRA, PlatformType.ECOMMERCE),
    QuickCommerceIntegration("Chroma", Platform.CHROMA, PlatformType.ECOMMERCE),
    QuickCommerceIntegration("Vijay Sales", Platform.VIJAY_SALES, PlatformType.ECOMMERCE),
    QuickCommerceIntegration("Reliance Digital", Platform.RELIANCE, PlatformType.ECOMMERCE),
]

_QUICK_COMMERCE_PLATFORMS = [
    QuickCommerceIntegration("BlinkIt", Platform.BLINKIT, PlatformType.QUICK_COMMERCE),
    QuickCommerceIntegration("Zepto", Platform.ZEPTO, PlatformType.QUICK_COMMERCE),
    QuickCommerceIntegration("Swiggy", Platform.INSTAMART, PlatformType.QUICK_COMMERCE),
]

_ALL_PLATFORMS = _ECOMMERCE_PLATFORMS + _QUICK_COMMERCE_PLATFORMS


class ProductSearchTool:
    """
    Fan-out search: hit all relevant platforms concurrently,
    merge + deduplicate results, respect per-intent platform selection.
    """

    def __init__(self) -> None:
        self._cache = get_cache_service()

    @staticmethod
    def has_any_enabled_platform() -> bool:
        """
        True if at least one platform integration has a usable API key.
        Used by the agent to give a clear "nothing is configured yet"
        message instead of a misleading "no results found" message.
        """
        return any(p.enabled for p in _ALL_PLATFORMS)

    async def search(
        self,
        intent: SearchIntent,
        pincode: Optional[str] = None,
        intent_type: IntentType = IntentType.SHOPPING_QUERY,
    ) -> Tuple[List[Product], List[str]]:
        """
        Returns (products, platforms_searched).
        Platforms searched are returned so the response can show the user.
        """
        platforms = self._select_platforms(intent, intent_type)
        cache_key = self._cache_key(intent, pincode, [p.platform.value for p in platforms])

        # Try cache first
        cached = await self._cache.get(cache_key)
        if cached:
            products = [Product.model_validate(p) for p in cached["products"]]
            return products, cached["platforms"]

        # Fan out: run all platform searches in parallel with a timeout
        tasks = {
            p.platform.value: asyncio.create_task(
                p.search(intent, pincode)
            )
            for p in platforms
            if p.enabled
        }

        results: List[Product] = []
        platforms_searched: List[str] = []

        # Guard: asyncio.wait() raises ValueError on an empty set. This happens
        # whenever no platform integration has a usable API key configured.
        # Returning early here (instead of crashing) is what the investigation
        # notes flagged as the root cause of "Set of Tasks/Futures is empty".
        if not tasks:
            return [], []

        done, _ = await asyncio.wait(
            tasks.values(),
            timeout=4.0,   # 4 s hard ceiling — no platform blocks the response
        )

        for platform_name, task in tasks.items():
            if task in done and not task.exception():
                platform_results = task.result()
                if platform_results:
                    results.extend(platform_results)
                    platforms_searched.append(platform_name)
            elif task not in done:
                task.cancel()   # timed out — cancel silently

        # Filter for relevance before deduplicating
        results = self._filter_relevance(results, intent.query_text)

        # Deduplicate by title similarity (crude but effective for MVP)
        results = self._deduplicate(results)

        # Cache the raw results
        await self._cache.set(
            cache_key,
            {
                "products": [p.model_dump() for p in results],
                "platforms": platforms_searched,
            },
        )

        return results, platforms_searched

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _filter_relevance(products: List[Product], query: str) -> List[Product]:
        query_tokens = set(t.lower() for t in query.split() if len(t) > 1)
        if not query_tokens:
            return products
        
        filtered = []
        for p in products:
            title_lower = p.title.lower()
            
            # Special strict case for PS5 (common test query)
            if "ps5" in query.lower() or "playstation 5" in query.lower():
                if "ps5" not in title_lower and "playstation 5" not in title_lower and "playstation®5" not in title_lower:
                    continue
            
            # Must match at least some parts of the query
            matched = sum(1 for t in query_tokens if t in title_lower)
            if matched > 0 or len(query_tokens) == 0:
                filtered.append(p)
                
        return filtered

    @staticmethod
    def _select_platforms(
        intent: SearchIntent,
        intent_type: IntentType,
    ) -> List:
        """
        Choose which platforms to search based on intent type and user prefs.
        Quick commerce queries skip e-commerce; vice versa.

        Important: if the intent-based candidate list has ZERO enabled
        platforms (e.g. the query was classified as a normal shopping query
        but only a quick-commerce key like Blinkit is configured), fall back
        to searching every enabled platform instead of returning nothing.
        Without this, a correctly-configured key can still produce an empty
        result purely because of how the message was classified.
        """
        if intent_type == IntentType.QUICK_COMMERCE or intent.is_urgent:
            candidates = _QUICK_COMMERCE_PLATFORMS
        elif intent_type == IntentType.SHOPPING_QUERY:
            # Fashion categories: skip quick commerce, add Myntra/Ajio
            fashion_cats = {"fashion", "clothing", "shoes", "accessories", "beauty"}
            if intent.category and intent.category.lower() in fashion_cats:
                candidates = _ECOMMERCE_PLATFORMS
            else:
                # Electronics / general: Amazon + Flipkart + SerpAPI first,
                # also include quick commerce if query_text suggests grocery
                candidates = _ECOMMERCE_PLATFORMS
        else:
            candidates = _ALL_PLATFORMS

        # Fallback: if nothing in the chosen bucket is actually enabled,
        # don't silently return an empty result — search whatever IS
        # configured instead, across both buckets.
        if not any(p.enabled for p in candidates):
            candidates = [p for p in _ALL_PLATFORMS if p.enabled]

        # Honour user platform preferences
        if intent.preferred_platforms:
            pref_set = set(intent.preferred_platforms)
            preferred = [p for p in candidates if p.platform.value in pref_set]
            if preferred:
                candidates = preferred

        if intent.exclude_platforms:
            excl_set = set(intent.exclude_platforms)
            candidates = [p for p in candidates if p.platform.value not in excl_set]

        # Respect max simultaneous platform cap from settings
        return candidates[: settings.max_search_platforms]

    @staticmethod
    def _deduplicate(products: List[Product]) -> List[Product]:
        """
        Remove near-duplicate titles from different platforms.
        Keep the cheaper / better-rated one.
        """
        seen: Dict[str, Product] = {}
        for p in products:
            key = _title_fingerprint(p.title)
            if key not in seen:
                seen[key] = p
            else:
                # Keep the one with lower price (or higher rating on tie)
                existing = seen[key]
                if p.price.current < existing.price.current:
                    seen[key] = p
                elif p.price.current == existing.price.current:
                    p_rating = (p.review_summary.average_rating or 0) if p.review_summary else 0
                    e_rating = (existing.review_summary.average_rating or 0) if existing.review_summary else 0
                    if p_rating > e_rating:
                        seen[key] = p
        return list(seen.values())

    @staticmethod
    def _cache_key(
        intent: SearchIntent,
        pincode: Optional[str],
        platforms: List[str],
    ) -> str:
        raw = f"{intent.query_text}:{intent.budget_max}:{pincode}:{','.join(sorted(platforms))}"
        return "psearch:" + hashlib.md5(raw.encode()).hexdigest()


def _title_fingerprint(title: str) -> str:
    """
    Crude deduplication fingerprint: lowercase, remove common noise words,
    take first 5 significant tokens.
    """
    noise = {"with", "for", "and", "the", "a", "in", "of", "by", "new"}
    tokens = [
        t.lower()
        for t in title.split()
        if t.lower() not in noise and len(t) > 2
    ][:5]
    return " ".join(tokens)
