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
from squirrel_commercial.estimator import estimate_input
from squirrel_commercial.schema import requests, keys
from app.config import get_settings
from app.common.errors import AppError

request_id = ContextVar('commercial_request_id', default=None)
account_id = ContextVar('commercial_account_id', default=None)

def translate(exc):
    error = AppError(message=exc.code, code=exc.code, status_code=exc.status)
    if exc.code == 'price_sync_pending':
        error.headers = {'Retry-After': '1'}
    return error

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
        try:
            input_bound, estimator_version = estimate_input(body)
        except core.BillingError as exc:
            raise translate(exc) from exc
        rid = str(uuid.uuid4())
        try:
            await core.reserve(engine, rid, key_id, body.get('model', ''), input_bound, output, estimator_version)
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
                interrupted = isinstance(exc, (asyncio.CancelledError, TimeoutError, GeneratorExit))
                with anyio.CancelScope(shield=True):
                    await core.settle(engine, rid, core.UsageEvidence(interrupted=interrupted, estimated_input=input_bound, estimated_output=0))
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
    interrupted = details.get('interrupted') is True or log.response_status == 499
    reliable = details.get('source') == 'upstream' and (details.get('final_usage') is True if log.is_stream else details.get('response_complete') is True)
    evidence = core.UsageEvidence(
        input_tokens=log.input_tokens, output_tokens=log.output_tokens,
        source=details.get('source', 'unknown'), terminal_complete=reliable,
        interrupted=interrupted, has_output=bool(log.output_tokens),
        end_reason='interrupted' if interrupted else 'response',
        estimated_input=details.get('estimated_input_tokens', 0),
        estimated_output=details.get('estimated_output_tokens', 0))
    from dataclasses import asdict
    payload = dict(protocol_version=2, request_id=log.trace_id, evidence=asdict(evidence))
    path = None
    try:
        path = write_journal(payload)
    except OSError:
        logging.getLogger(__name__).error("Commercial recovery storage unavailable: %s", log.trace_id)
    await core.settle(engine, payload['request_id'], payload.get('evidence', {}))
    if path is not None:
        await discard_completed(engine, path, payload['request_id'])

def write_journal(payload, *, probe=False):
    import os
    import tempfile
    payload = {'protocol_version': 2, **payload}
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
    from squirrel_commercial.pricing import models, sync_price
    cursor = ''
    while True:
        async with engine.begin() as c:
            names = (await c.execute(select(models.c.requested_model).where(models.c.requested_model > cursor).order_by(models.c.requested_model).limit(100))).scalars().all()
            for name in names:
                await sync_price(c, name)
        if len(names) < 100:
            break
        cursor = names[-1]
    from itertools import islice
    for path in islice(Path(get_settings().COMMERCIAL_RECOVERY_DIR).glob('*.json'), 100):
        try:
            payload = json.loads(path.read_text())
            if payload.get('protocol_version') != 2:
                raise ValueError('incompatible journal protocol')
            async with engine.connect() as c:
                state = await c.scalar(select(requests.c.status).where(requests.c.id == payload['request_id']))
            if state in ('reserved', 'review'):
                await core.settle(engine, payload['request_id'], payload.get('evidence', {}))
            await discard_completed(engine, path, payload['request_id'])
        except (ValueError, KeyError, TypeError):
            quarantine = path.parent / 'quarantine'
            quarantine.mkdir(exist_ok=True, mode=0o700)
            path.replace(quarantine / path.name)
            logging.getLogger(__name__).error('Invalid commercial journal quarantined: %s', path.stem)
        except Exception:
            logging.getLogger(__name__).error("Commercial settlement recovery pending: %s", path.stem)
    import time
    archive = Path(get_settings().COMMERCIAL_RECOVERY_DIR) / 'review'
    for old in archive.glob('*.json'):
        if old.stat().st_mtime < time.time() - 30*86400:
            old.unlink(missing_ok=True)
    # A hard execution deadline is enforced by the wrapper. After a generous
    # grace interval, orphan reservations become review cases, never auto-refunded.
    from sqlalchemy import update
    async with engine.begin() as c:
        stale = (await c.execute(select(requests.c.id).where(requests.c.status == 'reserved', requests.c.updated_at < core.now()-10800).order_by(requests.c.updated_at, requests.c.id).limit(100).with_for_update(skip_locked=True))).scalars().all()
        if stale:
            await c.execute(update(requests).where(requests.c.id.in_(stale), requests.c.status == 'reserved').values(status='review', updated_at=core.now()))

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


def complete_usage(body):
    """Validate complete non-stream usage before normalized/coerced counters."""
    if isinstance(body, (str, bytes, bytearray)):
        try:
            body = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            return False
    if not isinstance(body, dict) or not isinstance(body.get('usage'), dict):
        return False
    usage = body['usage']
    if any(type(usage[k]) is not int or usage[k] < 0 for k in ('cache_read_input_tokens', 'cache_creation_input_tokens') if k in usage):
        return False
    for inp, out in (('prompt_tokens', 'completion_tokens'), ('input_tokens', 'output_tokens')):
        if all(type(usage.get(k)) is int and usage[k] >= 0 for k in (inp, out)):
            return True
    return False
