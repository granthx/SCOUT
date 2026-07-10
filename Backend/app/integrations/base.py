"""
app/integrations/base.py
─────────────────────────
Abstract base class for all platform integrations.
Each platform adapter (Amazon, Flipkart, Blinkit, …) inherits from this,
implements `search()`, and returns a list of unified Product objects.
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from typing import List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.models.intent import SearchIntent
from app.models.product import Platform, Product


class BaseIntegration(ABC):
    """
    All platform adapters share:
    - An async httpx client with a 10 s timeout
    - Retry logic (3 attempts, exponential back-off)
    - A cache-key helper
    """

    platform: Platform                          # must be set by subclass
    platform_type: str = "ecommerce"           # "ecommerce" | "quick_commerce"
    enabled: bool = True                        # set False if API key is missing

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(timeout=10.0)

    # ── Abstract ──────────────────────────────────────────────────────────────

    @abstractmethod
    async def search(
        self,
        intent: SearchIntent,
        pincode: Optional[str] = None,
    ) -> List[Product]:
        """
        Call the platform API and return a list of Product objects.
        Must not raise — return [] on any error.
        """
        ...

    # ── Shared helpers ────────────────────────────────────────────────────────

    @staticmethod
    def cache_key(platform: str, query: str, pincode: Optional[str]) -> str:
        raw = f"{platform}:{query}:{pincode or ''}"
        return "search:" + hashlib.md5(raw.encode()).hexdigest()

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=False,
    )
    async def _get(self, url: str, **kwargs) -> httpx.Response:
        return await self._http.get(url, **kwargs)

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=False,
    )
    async def _post(self, url: str, **kwargs) -> httpx.Response:
        return await self._http.post(url, **kwargs)

    async def close(self) -> None:
        await self._http.aclose()
