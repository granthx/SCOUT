"""
app/api/routes/health.py
─────────────────────────
GET /api/health  — service health and configuration status.
Useful for deployment health checks and debugging missing API keys.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.integrations.amazon import AmazonIntegration
from app.integrations.blinkit import BlinkitIntegration
from app.integrations.flipkart import FlipkartIntegration
from app.integrations.instamart import InstamartIntegration
from app.integrations.myntra_ajio import AjioIntegration, MyntraIntegration
from app.integrations.serp_api import SerpAPIIntegration
from app.integrations.zepto import ZeptoIntegration
from app.models.response import HealthResponse
from app.services.cache_service import get_cache_service

router = APIRouter(prefix="/api", tags=["health"])
settings = get_settings()

_ALL_INTEGRATIONS = [
    SerpAPIIntegration(),
    AmazonIntegration(),
    FlipkartIntegration(),
    MyntraIntegration(),
    AjioIntegration(),
    BlinkitIntegration(),
    ZeptoIntegration(),
    InstamartIntegration(),
]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """
    Returns the operational status of:
    - LLM connection (Anthropic API key set)
    - Platform integrations (which API keys are configured)
    - Cache connection (Redis or local)
    """
    llm_ok = settings.gemini_api_key not in ("", "ADD_API_HERE")
    configured_platforms = [
        i.platform.value for i in _ALL_INTEGRATIONS if i.enabled
    ]
    cache_ok = await get_cache_service().is_connected()

    return HealthResponse(
        status="ok" if llm_ok else "degraded",
        llm_connected=llm_ok,
        platforms_configured=configured_platforms,
        cache_connected=cache_ok,
        version="1.0.0",
    )


@router.get("/")
async def root() -> dict:
    return {
        "name": "Universal Commerce Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
