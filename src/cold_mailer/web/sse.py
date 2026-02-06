"""Server-Sent Events (SSE) for bulk email progress streaming."""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import AsyncGenerator

from fastapi import Request
from fastapi.responses import StreamingResponse


@dataclass
class BulkSendSession:
    """Session for tracking bulk send progress."""

    session_id: str
    total: int
    current: int = 0
    current_email: str = ""
    status: str = "pending"  # pending, in_progress, completed, error
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "total": self.total,
            "current": self.current,
            "current_email": self.current_email,
            "status": self.status,
            "sent": self.sent,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
        }


# Global session storage
_sessions: dict[str, BulkSendSession] = {}


def create_session(total: int) -> BulkSendSession:
    """Create a new bulk send session."""
    session_id = str(uuid.uuid4())
    session = BulkSendSession(session_id=session_id, total=total)
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> BulkSendSession | None:
    """Get a session by ID."""
    return _sessions.get(session_id)


def update_session(
    session_id: str,
    current: int | None = None,
    current_email: str | None = None,
    status: str | None = None,
    sent: int | None = None,
    failed: int | None = None,
    skipped: int | None = None,
    error: dict | None = None,
) -> BulkSendSession | None:
    """Update a session's progress."""
    session = _sessions.get(session_id)
    if not session:
        return None

    if current is not None:
        session.current = current
    if current_email is not None:
        session.current_email = current_email
    if status is not None:
        session.status = status
    if sent is not None:
        session.sent = sent
    if failed is not None:
        session.failed = failed
    if skipped is not None:
        session.skipped = skipped
    if error is not None:
        session.errors.append(error)

    return session


def delete_session(session_id: str) -> None:
    """Delete a session."""
    _sessions.pop(session_id, None)


async def stream_progress(session_id: str) -> AsyncGenerator[str, None]:
    """Stream progress updates for a bulk send session."""
    while True:
        session = get_session(session_id)
        if not session:
            yield f"data: {json.dumps({'error': 'Session not found'})}\n\n"
            break

        yield f"data: {json.dumps(session.to_dict())}\n\n"

        if session.status in ("completed", "error"):
            break

        await asyncio.sleep(0.5)


def create_sse_response(session_id: str) -> StreamingResponse:
    """Create an SSE streaming response for progress updates."""
    return StreamingResponse(
        stream_progress(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
