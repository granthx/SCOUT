"""
app/config.py
─────────────
Central settings object.  All values come from environment variables (or .env).
No hardcoded paths, keys, or platform URLs live anywhere else in the codebase.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    gemini_api_key: str = "ADD_API_HERE"
    llm_model: str = "gemini-2.0-flash"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.2

    # ── Search ────────────────────────────────────────────────────────────────
    serp_api_key: str = "ADD_API_HERE"
    serp_api_base_url: str = "https://serpapi.com/search"

    # ── Amazon ────────────────────────────────────────────────────────────────
    amazon_affiliate_tag: str = "ADD_API_HERE"
    amazon_access_key: str = "ADD_API_HERE"
    amazon_secret_key: str = "ADD_API_HERE"
    amazon_partner_tag: str = "ADD_API_HERE"

    # ── Flipkart ──────────────────────────────────────────────────────────────
    flipkart_affiliate_id: str = "ADD_API_HERE"
    flipkart_affiliate_token: str = "ADD_API_HERE"

    # ── Myntra / Ajio / Nykaa ────────────────────────────────────────────────
    # Via Admitad / VCommission affiliate feeds. Needs BOTH a token AND a
    # feed URL from your affiliate dashboard — there is no public default.
    myntra_affiliate_token: str = "ADD_API_HERE"
    myntra_feed_url: str = "ADD_API_HERE"
    ajio_affiliate_token: str = "ADD_API_HERE"
    ajio_feed_url: str = "ADD_API_HERE"
    nykaa_affiliate_token: str = "ADD_API_HERE"

    # ── Quick Commerce ────────────────────────────────────────────────────────
    # NOTE: Blinkit, Zepto and Instamart do not have public self-serve APIs.
    # Both the *_API_KEY and *_API_BASE_URL must come from an approved partner
    # / licensed data provider — there is no working default. Leave these as
    # "ADD_API_HERE" until you actually have partner credentials; the
    # integration will simply stay disabled (and be skipped) until then.
    blinkit_api_key: str = "ADD_API_HERE"
    blinkit_api_base_url: str = "ADD_API_HERE"

    zepto_api_key: str = "ADD_API_HERE"
    zepto_api_base_url: str = "ADD_API_HERE"

    instamart_api_key: str = "ADD_API_HERE"
    instamart_api_base_url: str = "ADD_API_HERE"

    zomato_api_key: str = "ADD_API_HERE"
    zomato_api_base_url: str = "ADD_API_HERE"

    quickcommerce_api_key: str = "ADD_API_HERE"
    quickcommerce_api_base_url: str = "https://api.quickcommerceapi.com/v1"

    # ── Cache ─────────────────────────────────────────────────────────────────
    redis_url: str = ""                     # empty → fall back to in-memory
    cache_ttl_seconds: int = 300

    # ── Sessions ──────────────────────────────────────────────────────────────
    app_secret_key: str = "ADD_API_HERE"
    session_ttl_seconds: int = 3600

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = "development"
    rate_limit_per_minute: int = 30
    max_search_platforms: int = 10

    # ── CORS ──────────────────────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: str) -> str:
        return v  # kept as str; split in main.py

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a singleton Settings instance (cached after first call)."""
    return Settings()
