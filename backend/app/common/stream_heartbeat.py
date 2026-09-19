"""Keep an idle downstream stream alive without cancelling its upstream read."""

import asyncio
from typing import AsyncGenerator

import anyio


async def with_heartbeat(
    stream: AsyncGenerator[bytes, None], *, interval: float, heartbeat: bytes
) -> AsyncGenerator[bytes, None]:
    """Own one outstanding read; cancel and collect it before closing the stream.

    Timeouts measure downstream silence, not upstream activity. In particular,
    a converter may consume many upstream chunks without yielding any output.
    No additional reads are scheduled while the consumer is paused at a yield.
    """
    if interval <= 0:
        raise ValueError("Heartbeat interval must be positive")
    pending = None
    try:
        while True:
            if pending is None:
                pending = asyncio.create_task(anext(stream))
            done, _ = await asyncio.wait({pending}, timeout=interval)
            if not done:
                yield heartbeat
                continue
            completed, pending = pending, None
            try:
                chunk = completed.result()
            except StopAsyncIteration:
                return
            yield chunk
    finally:
        # ASGI disconnects use level cancellation: every cleanup await would
        # otherwise be cancelled again, potentially orphaning the pending read.
        with anyio.CancelScope(shield=True):
            if pending is not None:
                pending.cancel()
                # Also retrieve an exception if the read completed while paused
                # at a heartbeat yield, without replacing a consumer cancellation.
                await asyncio.gather(pending, return_exceptions=True)
            await stream.aclose()
