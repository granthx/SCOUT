"""
app/services/llm_service.py
────────────────────────────
Async wrapper around the Anthropic Claude API.
All LLM calls go through here — swap providers here if needed.
"""
from __future__ import annotations

import json
import re
from typing import Any, AsyncIterator, Dict, List, Optional



from app.config import get_settings

settings = get_settings()

from google import genai
class LLMService:
    """Singleton-style service; instantiate once in lifespan."""

    def __init__(self) -> None:
        self._client = genai.Client(
     api_key=settings.gemini_api_key
        )


    # ── Core: streaming ───────────────────────────────────────────────────────

    async def stream(
        self,
        messages: List[Dict[str, str]],
        system: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        """Yield text tokens as they arrive from Claude."""
        async with self._client.messages.stream(
            model=settings.llm_model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            temperature=temperature,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    # ── Core: full completion ────────────────────────────────────────────────

    async def complete(
        self,
        messages: List[Dict[str, str]],
        system: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        """Return the full text of a single completion."""
        response = await self._client.messages.create(
            model=settings.llm_model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            temperature=temperature,
        )
        return response.content[0].text

    # ── Structured JSON output ────────────────────────────────────────────────

    async def complete_json(
        self,
        messages: List[Dict[str, str]],
        system: str = "",
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """
        Request JSON output from Claude and parse it safely.
        The system prompt should instruct the model to respond with ONLY JSON.
        """
        system_with_json = (
            system
            + "\n\nIMPORTANT: Respond with ONLY valid JSON. "
            "No markdown, no explanation, no backticks."
        )
        raw = await self.complete(
            messages=messages,
            system=system_with_json,
            max_tokens=max_tokens,
            temperature=0.0,   # deterministic for structured outputs
        )
        # Strip any accidental markdown fences
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"LLM did not return valid JSON.\nRaw: {raw}\nError: {exc}"
            ) from exc


# ── Module-level singleton ────────────────────────────────────────────────────

_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
