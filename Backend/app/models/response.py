"""
app/models/response.py
──────────────────────
Request / response contracts for the REST API.
Frontend reads these — keep them stable.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.product import ProductCard


# ── Inbound ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = None     # None → server creates a new session
    pincode: Optional[str] = None        # user's delivery pincode
    city: Optional[str] = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    pincode: Optional[str] = None
    budget_max: Optional[float] = None
    platforms: Optional[List[str]] = None
    sort_by: str = "best_value"
    page: int = 1
    page_size: int = 10


# ── Outbound (SSE chunk payloads) ────────────────────────────────────────────

class ChunkType(str, Enum):
    TEXT = "text"               # streaming text token
    PRODUCTS = "products"       # product card list
    INTENT = "intent"           # echo back parsed intent (debug/UX)
    THINKING = "thinking"       # "Searching across platforms…" status
    ERROR = "error"
    DONE = "done"               # signals stream end


class StreamChunk(BaseModel):
    type: ChunkType
    data: Any = None
    session_id: Optional[str] = None


# ── Outbound (non-streaming) ─────────────────────────────────────────────────

class SearchResponse(BaseModel):
    query: str
    intent_type: str
    products: List[ProductCard] = Field(default_factory=list)
    total_found: int = 0
    platforms_searched: List[str] = Field(default_factory=list)
    ai_summary: Optional[str] = None
    best_pick: Optional[ProductCard] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    llm_connected: bool = False
    platforms_configured: List[str] = Field(default_factory=list)
    cache_connected: bool = False
    version: str = "1.0.0"
