"""
app/main.py
────────────
FastAPI application factory.
- Lifespan: initialises singletons on startup
- CORS: configured from environment (no hardcoded origins)
- Routes: /api/chat, /api/search, /api/health
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.core import get_commerce_agent
from app.api.routes import chat, health, search
from app.config import get_settings
from app.services.cache_service import get_cache_service
from app.services.llm_service import get_llm_service
from app.services.session_service import get_session_service

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialise all singletons on startup so the first request doesn't pay
    the cold-start cost.
    """
    # Warm up singletons
    get_llm_service()
    get_cache_service()
    get_session_service()
    get_commerce_agent()

    from app.tools.product_search import _ALL_PLATFORMS  # local import avoids cycle

    active = [p.platform.value for p in _ALL_PLATFORMS if p.enabled]
    print("✅ Universal Commerce Agent started")
    print(f"   Environment : {settings.app_env}")
    print(f"   LLM model   : {settings.llm_model}")
    if active:
        print(f"   Platforms   : {', '.join(active)}")
    else:
        print(
            "   Platforms   : none configured — set at least SERP_API_KEY in "
            ".env to enable product search, then restart."
        )
    yield
    # Cleanup (if needed)
    print("🛑 Universal Commerce Agent shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Universal Commerce Agent API",
        description=(
            "AI-powered cross-platform shopping assistant for India. "
            "Searches Amazon, Flipkart, Blinkit, Zepto, Instamart, Myntra, and Ajio "
            "simultaneously, ranks results, and summarises reviews."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(search.router)

    return app


app = create_app()
