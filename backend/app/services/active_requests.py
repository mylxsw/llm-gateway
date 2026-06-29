"""
Active Request Tracker

Stores asyncio.Task references for in-progress proxy requests so
they can be cancelled via the admin API.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ActiveRequestTracker:
    """Thread-safe tracker for active (in-progress) request tasks.

    Stores asyncio.Task references keyed by log_id.  When a request
    arrives a task is registered; when it completes (or is cancelled)
    the task is deregistered.  The admin cancel endpoint calls
    cancel() to both cancel the underlying asyncio.Task and pop it
    from the tracker atomically.
    """

    def __init__(self) -> None:
        self._tasks: dict[int, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def register(self, log_id: int, task: asyncio.Task) -> None:
        """Register a running task for the given log ID."""
        async with self._lock:
            self._tasks[log_id] = task

    async def deregister(self, log_id: int) -> None:
        """Remove the task (call after completion or cancellation)."""
        async with self._lock:
            self._tasks.pop(log_id, None)

    async def cancel(self, log_id: int) -> bool:
        """Cancel the task for the given log ID and remove it atomically.

        Returns True if a task was found and cancelled, False otherwise.
        """
        async with self._lock:
            task = self._tasks.pop(log_id, None)
        if task is None:
            return False
        task.cancel()
        logger.info("Cancelled active request: log_id=%d", log_id)
        return True

    async def is_active(self, log_id: int) -> bool:
        """Check whether a task is currently registered for the given log ID."""
        async with self._lock:
            return log_id in self._tasks


# Global singleton
active_requests = ActiveRequestTracker()
