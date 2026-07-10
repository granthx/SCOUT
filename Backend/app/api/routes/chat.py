"""
app/api/routes/chat.py
───────────────────────
POST /api/chat  — streaming Server-Sent Events (SSE) endpoint.

Frontend integration:
    const es = new EventSource('/api/chat', { method: 'POST', ... });
    es.onmessage = (e) => {
        const chunk = JSON.parse(e.data);
        if (chunk.type === 'text')     appendToken(chunk.data);
        if (chunk.type === 'products') renderProductCards(chunk.data.products);
        if (chunk.type === 'thinking') showLoadingBadge(chunk.data.message);
        if (chunk.type === 'done')     es.close();
    };

Or use fetch + ReadableStream for more control:
    const res = await fetch('/api/chat', { method:'POST', body: JSON.stringify({...}) });
    const reader = res.body.getReader();
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse

from app.agent.core import CommerceAgent, get_commerce_agent
from app.models.response import ChatRequest
from app.services.session_service import SessionService, get_session_service

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    agent: CommerceAgent = Depends(get_commerce_agent),
    session_svc: SessionService = Depends(get_session_service),
) -> EventSourceResponse:
    """
    Streaming chat endpoint.
    Accepts JSON body: { message, session_id?, pincode?, city? }
    Returns: Server-Sent Events stream of StreamChunk objects.
    """
    if not body.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="message cannot be empty",
        )

    # Load or create an isolated per-user session
    session = await session_svc.get_or_create(body.session_id)

    # Apply location hints from request
    if body.pincode:
        session.context.user_pincode = body.pincode
    if body.city:
        session.context.user_city = body.city

    async def event_generator():
        try:
            async for chunk in agent.handle(
                message=body.message,
                session=session,
                pincode=body.pincode or session.context.user_pincode,
            ):
                # Inject session_id on every chunk so the frontend can persist it
                chunk.session_id = session.session_id
                yield {
                    "event": chunk.type.value,
                    "data": json.dumps(chunk.model_dump()),
                }
        except Exception as exc:
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "data": str(exc)}),
            }
        finally:
            # Always persist session after each turn
            await session_svc.save(session)

    return EventSourceResponse(event_generator())


@router.delete("/session/{session_id}")
async def clear_session(
    session_id: str,
    session_svc: SessionService = Depends(get_session_service),
) -> dict:
    """Delete a session and its conversation history."""
    await session_svc.delete(session_id)
    return {"deleted": True, "session_id": session_id}
