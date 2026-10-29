"""Optional integration; ordinary installations never query commercial tables."""
import asyncio
import functools
import inspect
import json
import uuid
import logging
import anyio
from starlette.responses import StreamingResponse
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

def apply_stream_usage(body, protocol, options=None):
    if protocol != 'openai' or not body.get('stream'):
        return body
    body = dict(body)
    if (options or {}).get('supports_stream_usage') is False:
        body.pop('stream_options', None)
    else:
        body['stream_options'] = {**(body.get('stream_options') or {}), 'include_usage': True}
    return body


class CommercialStream:
    """Own the primed proxy generator, including before its first client read."""
    def __init__(self, stream, rid, uid, engine, owner):
        self.stream, self.rid, self.uid = stream, rid, uid
        self.engine, self.owner = engine, owner
        self.closed = False
        self.deadline = asyncio.get_running_loop().time() + 3600

    def __aiter__(self):
        return self

    async def __anext__(self):
        r = request_id.set(self.rid)
        a = account_id.set(self.uid)
        try:
            if asyncio.get_running_loop().time() >= self.deadline:
                raise TimeoutError
            async with asyncio.timeout_at(self.deadline):
                return await anext(self.stream)
        except BaseException:
            await self.aclose()
            raise
        finally:
            request_id.reset(r)
            account_id.reset(a)

    async def aclose(self):
        if self.closed:
            return
        self.closed = True
        r = request_id.set(self.rid)
        a = account_id.set(self.uid)
        try:
            with anyio.CancelScope(shield=True):
                try:
                    await self.stream.aclose()
                finally:
                    # Idempotent fallback if logging failed before journal creation.
                    try:
                        await core.settle(self.engine, self.rid)
                    except Exception:
                        logging.getLogger(__name__).error('Commercial request requires recovery: %s', self.rid)
        finally:
            if hasattr(self.owner, '_commercial_identities'):
                self.owner._commercial_identities.pop(self.rid, None)
            request_id.reset(r)
            account_id.reset(a)


class SettlingStreamingResponse(StreamingResponse):
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            if isinstance(self.body_iterator, CommercialStream):
                await self.body_iterator.aclose()


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
        if bound.arguments.get('admin_model_test') and key_id is None:
            return await fn(*args, **kwargs)
        async with engine.connect() as c:
            key = (await c.execute(select(keys).where(keys.c.api_key_id == key_id))).mappings().first()
        if not key:
            if settings.COMMERCIAL_ONLY:
                raise AppError('Commercial key required', code='commercial_key_required', status_code=403)
            return await fn(*args, **kwargs)
        async with engine.connect() as c:
            detail_enabled = await c.scalar(text('SELECT record_details FROM api_keys WHERE id=:id'), {'id': key_id})
        bound.arguments['record_details'] = bool(detail_enabled)
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
        stream_owned = False
        try:
            async with asyncio.timeout(3600):
                result = await fn(*bound.args, **bound.kwargs)
            if fn.__name__ == 'process_request_stream':
                response, stream, info = result
                stream_owned = True
                return response, CommercialStream(stream, rid, key['account_id'], engine, bound.arguments.get('self')), info
            return result
        except BaseException as exc:
            # Conservative: a thrown exception does not prove the upstream did no work.
            try:
                from app.common.token_counter import get_token_counter
                interrupted = isinstance(exc, (asyncio.CancelledError, TimeoutError, GeneratorExit))
                estimated = get_token_counter(bound.arguments.get('request_protocol', 'openai')).count_request(body, body.get('model', '')) if interrupted else None
                with anyio.CancelScope(shield=True):
                    await core.settle(engine, rid, estimated, 0 if interrupted else None)
            except Exception:
                logging.getLogger(__name__).error("Commercial request requires recovery: %s", rid)
            raise
        finally:
            owner = bound.arguments.get('self')
            if hasattr(owner, '_commercial_identities') and not stream_owned:
                owner._commercial_identities.pop(rid, None)
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
    interrupted = details.get('interrupted') is True or log.response_status in (499, 504)
    reliable = details.get('source') == 'upstream' and (not log.is_stream or details.get('final_usage') is True)
    failed = bool(log.response_status and log.response_status >= 400)
    initial_rejection = log.is_stream and failed and details.get('stream_started') is False
    has_usage = bool((log.output_tokens or 0) > 0 or (details.get('source') in ('upstream', 'mixed') and (log.input_tokens or 0) > 0))
    billable = not initial_rejection and (reliable or interrupted or (log.is_stream and (not failed or has_usage)))
    payload = dict(request_id=log.trace_id,
        input_tokens=(log.input_tokens or 0) if billable else None,
        output_tokens=(log.output_tokens or 0) if billable else None,
        failed=initial_rejection or (failed and not log.is_stream and not reliable and not interrupted))
    path = None
    try:
        path = write_journal(payload)
    except OSError:
        logging.getLogger(__name__).error("Commercial recovery storage unavailable: %s", log.trace_id)
    await core.settle(engine, **payload)
    if path is not None:
        await discard_completed(engine, path, payload['request_id'])

def write_journal(payload, *, probe=False):
    import os
    import tempfile
    directory = Path(get_settings().COMMERCIAL_RECOVERY_DIR)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / (payload['request_id'] + ('.probe' if probe else '.json'))
    fd, temporary = tempfile.mkstemp(prefix='settlement-', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(payload, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return path

async def discard_completed(engine, path, rid):
    async with engine.connect() as c:
        state = await c.scalar(select(requests.c.status).where(requests.c.id == rid))
    if state == 'review':
        archive = path.parent / 'review'
        archive.mkdir(exist_ok=True, mode=0o700)
        path.replace(archive / path.name)
    elif state in ('settled', 'cancelled'):
        path.unlink(missing_ok=True)

async def recover():
    if not get_settings().COMMERCIAL_ENABLED:
        return
    from app.db.session import engine
    for path in Path(get_settings().COMMERCIAL_RECOVERY_DIR).glob('*.json'):
        try:
            payload = json.loads(path.read_text())
            async with engine.connect() as c:
                state = await c.scalar(select(requests.c.status).where(requests.c.id == payload['request_id']))
            if state in ('reserved', 'review'):
                await core.settle(engine, **payload)
            await discard_completed(engine, path, payload['request_id'])
        except Exception:
            logging.getLogger(__name__).error("Commercial settlement recovery pending: %s", path.stem)
    async with engine.connect() as c:
        pending = select(resolutions).join(
            requests, requests.c.id == resolutions.c.request_id
        ).where(requests.c.status.in_(('reserved', 'review')))
        decisions = (await c.execute(pending)).mappings().all()
    for decision in decisions:
        try:
            if decision['action'] == 'waive':
                await core.settle(engine, decision['request_id'], failed=True)
        except Exception:
            logging.getLogger(__name__).error('Commercial resolution recovery pending: %s', decision['request_id'])
    # A hard execution deadline is enforced by the wrapper. After a generous
    # grace interval, orphan reservations become review cases, never auto-refunded.
    from sqlalchemy import update
    async with engine.begin() as c:
        await c.execute(update(requests).where(requests.c.status == 'reserved', requests.c.created_at < core.now()-10800).values(status='review', updated_at=core.now()))

class CommercialPrivacyMiddleware:
    """Keep redaction active through authentication, error handlers and response send."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        value = headers.get(b'x-api-key') or headers.get(b'authorization', b'')
        if value.lower().startswith(b'bearer '):
            value = value[7:]
        if not value.startswith(b'sqb-'):
            return await self.app(scope, receive, send)
        token = request_id.set(str(uuid.uuid4()))
        try:
            await self.app(scope, receive, send)
        finally:
            request_id.reset(token)
