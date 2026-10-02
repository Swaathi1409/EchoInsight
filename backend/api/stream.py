"""
SSE (Server-Sent Events) replay endpoint.

GET /api/v1/conversations/{id}/stream
Streams all existing turns as SSE events, then keeps connection open
for new turn events (by polling the DB every 2s for up to 5 minutes).

Event types:
  turn        — a transcript turn
  provisional — provisional state snapshot (sent after each appended turn)
  analysis    — final analysis ready
  done        — conversation ended and analysis complete; closes stream
  ping        — keepalive every 10s
"""
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from backend.api.deps import get_current_user
from backend.db import _db_session_dependency, get_db_session
from backend.models import Conversation, Turn, Analysis
from backend.api.conversations import _get_or_404, _turn_resp, _analysis_resp
from backend.models import QAResult, Commitment
from backend.domain_model import ConversationStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["stream"])

_POLL_INTERVAL = 2.0   # seconds between DB polls
_MAX_STREAM_SECONDS = 300  # 5 minutes max stream


def _sse(event: str, data: dict | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


@router.get("/conversations/{conv_id}/stream")
async def stream_conversation(
    conv_id: str,
    from_turn: int = 0,  # replay from turn index (0 = all)
    user=Depends(get_current_user),
) -> StreamingResponse:
    """
    SSE stream for a conversation.
    Replays existing turns then follows new turns in real-time.
    """
    # Verify conversation access (one-shot session for auth)
    async with get_db_session() as session:
        conv = await session.get(Conversation, conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

    async def event_generator():
        seen_turn_ids: set[str] = set()
        start_time = asyncio.get_event_loop().time()
        ping_counter = 0

        try:
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > _MAX_STREAM_SECONDS:
                    yield _sse("done", {"reason": "max_stream_duration"})
                    break

                async with get_db_session() as session:
                    # Fetch new turns
                    turns = (await session.execute(
                        select(Turn)
                        .where(Turn.conversation_id == conv_id)
                        .order_by(Turn.turn_index)
                    )).scalars().all()

                    new_turns = [t for t in turns if t.turn_id not in seen_turn_ids]
                    for t in new_turns:
                        seen_turn_ids.add(t.turn_id)
                        yield _sse("turn", {
                            "turn_id": t.turn_id,
                            "speaker": t.speaker,
                            "text": t.text_redacted,
                            "turn_index": t.turn_index,
                            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                        })

                    # Check if conversation ended with final analysis
                    conv = await session.get(Conversation, conv_id)
                    if conv and conv.status == ConversationStatus.ENDED.value:
                        an = (await session.execute(
                            select(Analysis)
                            .where(Analysis.conversation_id == conv_id)
                            .order_by(Analysis.version.desc()).limit(1)
                        )).scalar_one_or_none()

                        if an:
                            qa = (await session.execute(
                                select(QAResult).where(QAResult.analysis_id == an.analysis_id)
                            )).scalar_one_or_none()
                            com_rows = (await session.execute(
                                select(Commitment).where(Commitment.conversation_id == conv_id, Commitment.provisional == False)
                            )).scalars().all()
                            from backend.api.conversations import _analysis_resp
                            yield _sse("analysis", _analysis_resp(an, qa, com_rows))
                            yield _sse("done", {"reason": "conversation_ended"})
                            break

                    # Provisional state
                    if conv and conv.provisional_state_json and new_turns:
                        yield _sse("provisional", conv.provisional_state_json)

                # Keepalive ping every 10s
                ping_counter += 1
                if ping_counter % 5 == 0:
                    yield _sse("ping", {"ts": datetime.now(timezone.utc).isoformat()})

                await asyncio.sleep(_POLL_INTERVAL)

        except asyncio.CancelledError:
            logger.debug("SSE stream cancelled for conv %s", conv_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
