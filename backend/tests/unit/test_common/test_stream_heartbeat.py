import asyncio

import pytest

from app.common.stream_heartbeat import with_heartbeat


async def next_event(stream):
    return await asyncio.wait_for(anext(stream), timeout=1)


async def test_idle_pings_preserve_the_same_pending_read_and_order():
    release = asyncio.Event()
    closed = asyncio.Event()
    reads = 0

    async def upstream():
        nonlocal reads
        try:
            yield b"first"
            reads += 1
            await release.wait()
            yield b"second"
        finally:
            closed.set()

    stream = with_heartbeat(upstream(), interval=0.005, heartbeat=b"ping")
    try:
        assert await next_event(stream) == b"first"
        assert await next_event(stream) == b"ping"
        assert await next_event(stream) == b"ping"
        assert reads == 1 and not closed.is_set()
        release.set()
        assert await next_event(stream) == b"second"
        with pytest.raises(StopAsyncIteration):
            await next_event(stream)
        assert closed.is_set()
    finally:
        await stream.aclose()


@pytest.mark.parametrize("cancel_read", [False, True])
async def test_disconnect_collects_pending_read_and_closes_input(cancel_read):
    reading = asyncio.Event()
    closed = asyncio.Event()

    async def upstream():
        try:
            reading.set()
            await asyncio.Event().wait()
            yield b"unreachable"
        finally:
            closed.set()

    stream = with_heartbeat(
        upstream(), interval=60 if cancel_read else 0.005, heartbeat=b"ping"
    )
    if cancel_read:
        consumer = asyncio.create_task(anext(stream))
        await asyncio.wait_for(reading.wait(), 1)
        consumer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer
    else:
        assert await next_event(stream) == b"ping"
        await stream.aclose()
    assert closed.is_set()


async def test_slow_consumer_does_not_prefetch_and_close_after_data_closes_input():
    reads = 0
    closed = False

    async def upstream():
        nonlocal reads, closed
        try:
            while True:
                reads += 1
                yield b"data"
        finally:
            closed = True

    stream = with_heartbeat(upstream(), interval=0.005, heartbeat=b"ping")
    assert await next_event(stream) == b"data"
    await asyncio.sleep(0)
    assert reads == 1
    await stream.aclose()
    assert closed


@pytest.mark.parametrize("close_after_error", [False, True])
async def test_upstream_error_is_propagated_or_collected_on_close(close_after_error):
    release = asyncio.Event()
    raised = asyncio.Event()

    async def upstream():
        await release.wait()
        raised.set()
        raise RuntimeError("upstream failed")
        yield  # pragma: no cover

    stream = with_heartbeat(upstream(), interval=0.005, heartbeat=b"ping")
    assert await next_event(stream) == b"ping"
    release.set()
    await asyncio.wait_for(raised.wait(), 1)
    if close_after_error:
        await stream.aclose()
    else:
        with pytest.raises(RuntimeError, match="upstream failed"):
            await next_event(stream)


async def test_invalid_interval_is_rejected():
    async def upstream():
        yield b"data"

    with pytest.raises(ValueError, match="positive"):
        await anext(with_heartbeat(upstream(), interval=0, heartbeat=b"ping"))
