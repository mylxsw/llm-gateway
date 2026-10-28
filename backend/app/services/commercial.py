"""Optional integration; ordinary installations never query commercial tables."""
import asyncio
import functools
import inspect
import json
import uuid
from contextvars import ContextVar
from pathlib import Path
from sqlalchemy import select, text
from squirrel_commercial import core
from squirrel_commercial.schema import requests, keys, resolutions
from app.config import get_settings
from app.common.errors import AppError

request_id = ContextVar('commercial_request_id', default=None)
account_id = ContextVar('commercial_account_id', default=None)

def translate(exc):
    return AppError(message=exc.code, code=exc.code, status_code=exc.status)

def commercial_call(fn):
    signature = inspect.signature(fn)
    @functools.wraps(fn)
    async def wrapped(*args, **kwargs):
        settings = get_settings()
        if not settings.COMMERCIAL_ENABLED:
            return await fn(*args, **kwargs)
        from app.db.session import engine
        bound = signature.bind(*args, **kwargs)
        key_id = bound.arguments.get('api_key_id')
        async with engine.connect() as c:
            key = (await c.execute(select(keys).where(keys.c.api_key_id == key_id))).mappings().first()
        if not key:
            if settings.COMMERCIAL_ONLY:
                raise AppError('Commercial key required', code='commercial_key_required', status_code=403)
            return await fn(*args, **kwargs)
        async with engine.connect() as c:
            detail_enabled = await c.scalar(text('SELECT record_details FROM api_keys WHERE id=:id'), {'id': key_id})
        kwargs['record_details'] = bool(detail_enabled)
        body = bound.arguments['body']
        if bound.arguments['path'] not in ('/v1/chat/completions', '/v1/messages'):
            raise AppError('Interface not available for billing', code='unsupported_billing_interface', status_code=400)
        if 'max_completion_tokens' in body and 'max_tokens' in body:
            raise AppError('Use one output limit', code='ambiguous_output_limit', status_code=400)
        if body.get('n', 1) != 1:
            raise AppError('Only one completion supported', code='unsupported_completion_count', status_code=400)
        output = body.get('max_completion_tokens', body.get('max_tokens'))
        if type(output) is not int or output <= 0:
            raise AppError('Specify a positive max_tokens', code='max_tokens_required', status_code=400)
        # Text only: bound input by UTF-8 bytes plus framing; reject multimodal.
        messages = body.get('messages')
        if not isinstance(messages, list) or any(not isinstance(m, dict) or not isinstance(m.get('content'), str) for m in messages) or body.get('tools'):
            raise AppError('Only text messages are supported', code='unsupported_billing_input', status_code=400)
        input_bound = len(json.dumps(body, ensure_ascii=False).encode()) + 1024
        rid = str(uuid.uuid4())
        try:
            await core.reserve(engine, rid, key_id, body.get('model', ''), input_bound, output)
        except core.BillingError as exc:
            raise translate(exc) from exc
        context = request_id.set(rid)
        account_context = account_id.set(key["account_id"])
        try:
            async with asyncio.timeout(3600):
                result = await fn(*args, **kwargs)
            if fn.__name__ == 'process_request_stream':
                response, stream, info = result
                async def bounded_stream():
                    stream_context = request_id.set(rid)
                    stream_account = account_id.set(key['account_id'])
                    try:
                        async with asyncio.timeout(3600):
                            async for chunk in stream:
                                yield chunk
                    finally:
                        try:
                            await stream.aclose()
                        finally:
                            request_id.reset(stream_context)
                            account_id.reset(stream_account)
                return response, bounded_stream(), info
            return result
        except BaseException:
            # Conservative: a thrown exception does not prove the upstream did no work.
            await asyncio.shield(core.settle(engine, rid))
            raise
        finally:
            request_id.reset(context)
            account_id.reset(account_context)
    return wrapped

async def settle_log(log):
    if not get_settings().COMMERCIAL_ENABLED:
        return
    from app.db.session import engine
    if not log.commercial_user_id:
        return
    details = log.usage_details or {}
    # Estimates remain reviewable; never silently charge estimated tokens.
    reliable = details.get('source') == 'upstream'
    payload = dict(request_id=log.trace_id,
        input_tokens=log.input_tokens if reliable else None,
        output_tokens=log.output_tokens if reliable else None,
        failed=bool(log.response_status and log.response_status >= 400))
    directory = Path(get_settings().COMMERCIAL_RECOVERY_DIR)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / (log.trace_id + '.json')
    temporary = path.with_suffix('.tmp')
    import os
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(payload, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)
    await core.settle(engine, **payload)
    await discard_completed(engine, path, payload['request_id'])

async def discard_completed(engine, path, rid):
    async with engine.connect() as c:
        state = await c.scalar(select(requests.c.status).where(requests.c.id == rid))
    if state in ('settled', 'cancelled'):
        path.unlink(missing_ok=True)

async def recover():
    from app.db.session import engine
    for path in Path(get_settings().COMMERCIAL_RECOVERY_DIR).glob('*.json'):
        try:
            payload = json.loads(path.read_text())
            await core.settle(engine, **payload)
            await discard_completed(engine, path, payload['request_id'])
        except Exception:
            import logging
            logging.getLogger(__name__).error("Commercial settlement recovery pending: %s", path.stem)
    async with engine.connect() as c:
        decisions = (await c.execute(select(resolutions))).mappings().all()
    for decision in decisions:
        if decision['action'] == 'waive':
            await core.settle(engine, decision['request_id'], failed=True)
    # A hard execution deadline is enforced by the wrapper. After a generous
    # grace interval, orphan reservations become review cases, never auto-refunded.
    from sqlalchemy import update
    async with engine.begin() as c:
        await c.execute(update(requests).where(requests.c.status == 'reserved', requests.c.created_at < core.now()-10800).values(status='review', updated_at=core.now()))
