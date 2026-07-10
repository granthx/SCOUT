"""
tests/test_agent.py
────────────────────
Async tests for the core agent pipeline.
Run with: pytest tests/ -v --asyncio-mode=auto
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.router import IntentRouter
from app.models.intent import IntentType
from app.models.product import (
    DeliveryInfo, Platform, PlatformType, PriceInfo, Product, ReviewSummary
)
from app.models.intent import SearchIntent, SortPriority
from app.tools.product_ranker import ProductRanker


# ── Intent Router Tests ───────────────────────────────────────────────────────

class TestIntentRouter:

    @pytest.mark.asyncio
    async def test_chitchat_fast_path(self):
        router = IntentRouter()
        result = await router.route("hi")
        assert result == IntentType.CHITCHAT

    @pytest.mark.asyncio
    async def test_follow_up_fast_path(self):
        router = IntentRouter()
        result = await router.route("compare the two", has_prior_products=True)
        assert result == IntentType.FOLLOW_UP

    @pytest.mark.asyncio
    async def test_shopping_query_via_llm(self):
        router = IntentRouter()
        with patch(
            "app.services.llm_service.LLMService.complete_json",
            new_callable=AsyncMock,
            return_value={"intent_type": "shopping_query", "confidence": 0.95},
        ):
            result = await router.route("best wireless headphones under 3000")
            assert result == IntentType.SHOPPING_QUERY


# ── Product Ranker Tests ──────────────────────────────────────────────────────

class TestProductRanker:

    def _make_product(
        self, pid: str, price: float, rating: float = 4.0,
        reviews: int = 100, days: int = 3
    ) -> Product:
        return Product(
            product_id=pid,
            title=f"Product {pid}",
            platform=Platform.AMAZON,
            platform_type=PlatformType.ECOMMERCE,
            price=PriceInfo(current=price, original=price * 1.2),
            review_summary=ReviewSummary(
                average_rating=rating, total_reviews=reviews
            ),
            delivery=DeliveryInfo(estimated_days=days, label=f"{days} days"),
            product_url="https://amazon.in/test",
        )

    def test_rank_by_price_fit(self):
        ranker = ProductRanker()
        products = [
            self._make_product("A", price=3500),  # over budget
            self._make_product("B", price=2999),  # within budget
            self._make_product("C", price=1500),  # well within
        ]
        intent = SearchIntent(
            query_text="headphones",
            budget_max=3000,
            sort_priority=SortPriority.LOWEST_PRICE,
        )
        ranked = ranker.rank(products, intent)
        # Cheapest should rank highest with LOWEST_PRICE priority
        assert ranked[0].product_id == "C"

    def test_rank_assigns_scores(self):
        ranker = ProductRanker()
        products = [self._make_product("X", 1000, rating=4.5, reviews=500)]
        intent = SearchIntent(query_text="test", budget_max=2000)
        ranked = ranker.rank(products, intent)
        assert ranked[0].score is not None
        assert 0.0 <= ranked[0].score <= 1.0
        assert len(ranked[0].score_breakdown) == 6

    def test_out_of_stock_penalised(self):
        ranker = ProductRanker()
        in_stock = self._make_product("IS", 1000)
        out_of_stock = self._make_product("OOS", 1000)
        out_of_stock.in_stock = False

        intent = SearchIntent(query_text="test", budget_max=2000)
        ranked = ranker.rank([out_of_stock, in_stock], intent)
        assert ranked[0].product_id == "IS"


# ── Integration scaffold (replace mocks with real calls when APIs are ready) ──

class TestSearchIntegration:

    @pytest.mark.asyncio
    async def test_serp_api_returns_empty_when_key_missing(self):
        from app.integrations.serp_api import SerpAPIIntegration
        integration = SerpAPIIntegration()
        integration.enabled = False  # simulate missing API key
        results = await integration.search(
            SearchIntent(query_text="headphones")
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_blinkit_returns_empty_when_key_missing(self):
        from app.integrations.blinkit import BlinkitIntegration
        integration = BlinkitIntegration()
        integration.enabled = False
        results = await integration.search(
            SearchIntent(query_text="milk")
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_search_does_not_crash_when_no_platforms_enabled(self):
        """
        Regression test for 'Set of Tasks/Futures is empty' crash:
        ProductSearchTool.search() must return ([], []) instead of raising
        when every integration is disabled (no API keys configured).
        """
        from app.tools.product_search import ProductSearchTool

        tool = ProductSearchTool()
        assert tool.has_any_enabled_platform() in (True, False)  # just shouldn't raise

        products, platforms = await tool.search(
            SearchIntent(query_text="anything"),
            pincode="110001",
        )
        # With no real keys configured in the test environment this should
        # resolve cleanly rather than raising ValueError from asyncio.wait().
        assert isinstance(products, list)
        assert isinstance(platforms, list)

    def test_blinkit_requires_both_key_and_base_url(self):
        """
        Regression test: a key alone must not enable Blinkit — the base URL
        must also be a real (non-placeholder) value, since Blinkit has no
        public API and a key-only check previously masked broken config.
        """
        from app.integrations.blinkit import BlinkitIntegration
        from app.config import get_settings

        settings = get_settings()
        original_key = settings.blinkit_api_key
        original_url = settings.blinkit_api_base_url
        try:
            settings.blinkit_api_key = "some-real-looking-key"
            settings.blinkit_api_base_url = "ADD_API_HERE"
            assert BlinkitIntegration().enabled is False
        finally:
            settings.blinkit_api_key = original_key
            settings.blinkit_api_base_url = original_url

    def test_configured_platform_not_silently_skipped_by_intent_bucket(self):
        """
        Regression test: previously, if a user had ONLY a quick-commerce
        platform (e.g. Blinkit) configured and their message was classified
        as a normal SHOPPING_QUERY (the common case for most phrasing),
        _select_platforms() would only consider the e-commerce bucket —
        which had nothing enabled — and silently return an empty candidate
        list. The configured platform was never even attempted, producing a
        confusing empty result despite a valid key being set.

        _select_platforms() must now fall back to any enabled platform when
        the intent-based bucket has none enabled.
        """
        from app.tools.product_search import (
            ProductSearchTool,
            _ECOMMERCE_PLATFORMS,
            _QUICK_COMMERCE_PLATFORMS,
        )

        original_states = {
            id(p): p.enabled for p in (_ECOMMERCE_PLATFORMS + _QUICK_COMMERCE_PLATFORMS)
        }
        try:
            for p in _ECOMMERCE_PLATFORMS:
                p.enabled = False
            for p in _QUICK_COMMERCE_PLATFORMS:
                p.enabled = False
            _QUICK_COMMERCE_PLATFORMS[0].enabled = True  # only Blinkit configured

            intent = SearchIntent(query_text="buy me a laptop")
            selected = ProductSearchTool._select_platforms(
                intent, IntentType.SHOPPING_QUERY
            )
            selected_names = {p.platform.value for p in selected}

            assert _QUICK_COMMERCE_PLATFORMS[0].platform.value in selected_names
        finally:
            for p in (_ECOMMERCE_PLATFORMS + _QUICK_COMMERCE_PLATFORMS):
                p.enabled = original_states[id(p)]
