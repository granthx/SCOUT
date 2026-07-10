"""
app/models/session.py
─────────────────────
Per-user, isolated conversation session.
Fixes ShoppingGPT's critical flaw: a single global ConversationBufferMemory
shared across all visitors.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str                     # "user" | "assistant" | "system"
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionContext(BaseModel):
    """
    Carries cross-turn context so follow-up queries work correctly.
    E.g. "compare the first two" requires knowing what was shown.
    """

    last_intent_type: Optional[str] = None
    last_search_query: Optional[str] = None
    last_products_shown: List[Dict[str, Any]] = Field(default_factory=list)
    last_category: Optional[str] = None
    user_pincode: Optional[str] = None
    user_city: Optional[str] = None
    preferred_platforms: List[str] = Field(default_factory=list)


class Session(BaseModel):
    session_id: str
    messages: List[ChatMessage] = Field(default_factory=list)
    context: SessionContext = Field(default_factory=SessionContext)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def add_message(self, role: str, content: str, **metadata: Any) -> None:
        self.messages.append(
            ChatMessage(role=role, content=content, metadata=metadata)
        )
        self.last_active = datetime.now(timezone.utc)

    def get_history_for_llm(self, max_turns: int = 10) -> List[Dict[str, str]]:
        """Return the last N turns formatted for the Anthropic messages API."""
        recent = [m for m in self.messages if m.role != "system"][-max_turns * 2:]
        return [{"role": m.role, "content": m.content} for m in recent]
