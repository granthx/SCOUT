"""
app/api/routes/search.py
─────────────────────────
GET/POST /api/search  — non-streaming product search endpoint.
Useful for direct integrations, browser extensions, and B2B API clients.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.agent.core import CommerceAgent, get_commerce_agent
from app.models.intent import IntentType, SearchIntent, SortPriority
from app.models.product import ProductCard
from app.models.response import SearchResponse, SearchRequest
from app.tools.price_analyzer import PriceAnalyzer
from app.tools.product_ranker import ProductRanker
from app.tools.product_search import ProductSearchTool
from app.tools.review_summarizer import ReviewSummarizer

router = APIRouter(prefix="/api", tags=["search"])
_ranker = ProductRanker()
_summarizer = ReviewSummarizer()
_price_analyzer = PriceAnalyzer()


@router.post("/search", response_model=SearchResponse)
async def search_products(body: SearchRequest) -> SearchResponse:
    """
    Non-streaming product search.
    Returns ranked product cards with AI review summaries.

    Request body:
      { "query": "wireless headphones under 3000",
        "pincode": "110001",
        "budget_max": 3000,
        "sort_by": "best_value" }
    """
    searcher = ProductSearchTool()

    intent = SearchIntent(
        query_text=body.query,
        budget_max=body.budget_max,
        sort_priority=SortPriority(body.sort_by)
        if body.sort_by in SortPriority._value2member_map_
        else SortPriority.BEST_VALUE,
    )

    products, platforms = await searcher.search(
        intent,
        pincode=body.pincode,
        intent_type=IntentType.SHOPPING_QUERY,
    )

    ranked = _ranker.rank(products, intent)
    await _summarizer.enrich(ranked)

    # Pagination
    start = (body.page - 1) * body.page_size
    page_products = ranked[start : start + body.page_size]

    cards = [ProductCard.from_product(p) for p in page_products]
    best_pick = cards[0] if cards else None

    _, price_analysis = await _price_analyzer.analyse(ranked, body.query)

    return SearchResponse(
        query=body.query,
        intent_type=IntentType.SHOPPING_QUERY.value,
        products=cards,
        total_found=len(products),
        platforms_searched=platforms,
        ai_summary=price_analysis,
        best_pick=best_pick,
    )


@router.get("/search", response_model=SearchResponse)
async def search_products_get(
    q: str = Query(..., description="Product search query"),
    pincode: str = Query(None),
    budget: float = Query(None),
    sort: str = Query("best_value"),
    page: int = Query(1, ge=1),
) -> SearchResponse:
    """GET variant — handy for browser extension and quick API calls."""
    return await search_products(
        SearchRequest(
            query=q,
            pincode=pincode,
            budget_max=budget,
            sort_by=sort,
            page=page,
        )
    )
