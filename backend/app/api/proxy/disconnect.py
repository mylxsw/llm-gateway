"""Cancel proxy work when a client leaves before response headers."""

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

import anyio
from starlette.requests import Request

from app.common.errors import AppError

_T = TypeVar("_T")


async def until_disconnect(request: Request, work: Awaitable[_T]) -> _T:
    # The handler already consumed the request body. The streaming response will
    # take over listening for a disconnect once it starts.
    with anyio.CancelScope() as scope:
        async def watch_client():
            while (await request.receive())["type"] != "http.disconnect":
                pass
            scope.cancel()

        watcher = asyncio.create_task(watch_client())
        try:
            return await work
        finally:
            watcher.cancel()
            with anyio.CancelScope(shield=True):
                await asyncio.gather(watcher, return_exceptions=True)

    raise AppError("Client disconnected", code="client_disconnected", status_code=499)
