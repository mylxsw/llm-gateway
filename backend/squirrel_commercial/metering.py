"""Version 2 reservation, evidence, final settlement and operator decisions."""
import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from sqlalchemy import select, insert, update, func
from .schema import accounts, keys, requests, months, oauth_apps, oauth_grants, resolutions
from .validation import integer, BillingError
from .funds import state, save, event, offset_idle_debt, reference_lock
from .pricing import read_price
from .estimator import ESTIMATOR_VERSION


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class UsageEvidence:
    input_tokens: int | None = None
    output_tokens: int | None = None
    source: str = 'unknown'
    terminal_complete: bool = False
    sent_upstream: bool = True
    has_output: bool = False
    interrupted: bool = False
    estimated_input: int = 0
    estimated_output: int = 0
    end_reason: str = 'unknown'
    estimator_version: str = ESTIMATOR_VERSION

    def tokens(self, reservation):
        if not self.sent_upstream:
            if self.has_output or self.input_tokens or self.output_tokens:
                raise BillingError('invalid_usage_evidence', 400)
            return 0, 0
        reported = all(type(v) is int and v >= 0 for v in (self.input_tokens, self.output_tokens))
        if self.terminal_complete and self.source == 'upstream' and reported:
            return integer(self.input_tokens), integer(self.output_tokens)
        if self.interrupted:
            return (max(integer(self.input_tokens or 0), integer(self.estimated_input), reservation['input_estimate']),
                    max(integer(self.output_tokens or 0), integer(self.estimated_output)))
        return None


async def oauth_lock(c, key):
    if key['source'] != 'oauth':
        return None
    # App before account, then grant/Key. App transitions must use this same lock.
    app_id = await c.scalar(select(oauth_grants.c.app_id).where(oauth_grants.c.id == key['oauth_grant_id']))
    app = (await c.execute(select(oauth_apps).where(oauth_apps.c.id == app_id).with_for_update())).mappings().first()
    if app is None:
        raise BillingError('oauth_grant_disabled')
    return app


async def reserve(engine, request_id, key_id, model, input_bound, output_bound, estimator_version=ESTIMATOR_VERSION):
    from .core import key_state, account_lock, now, cost, check_version
    integer(input_bound); integer(output_bound, minimum=1)
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 64:
        raise BillingError('invalid_request_id', 400)
    await check_version(engine)
    payload_hash = fingerprint([key_id, model, input_bound, output_bound, estimator_version])
    error = None
    async with engine.begin() as c:
        key = await key_state(c, key_id)
        app = await oauth_lock(c, key)
        await account_lock(c, key['account_id'])
        key = await key_state(c, key_id)
        account = (await c.execute(select(accounts).where(accounts.c.id == key['account_id']))).mappings().one()
        from sqlalchemy import text
        active = await c.scalar(text('SELECT is_active FROM api_keys WHERE id=:id'), {'id': key_id})
        if not active or account['chargeback_frozen']:
            raise BillingError('commercial_key_disabled')
        owner_type, owner_id, limit = 'key', str(key_id), key['monthly_limit_microcredits']
        eligible = True
        if app:
            grant = (await c.execute(select(oauth_grants).where(oauth_grants.c.id == key['oauth_grant_id']).with_for_update())).mappings().one()
            if (grant['account_id'] != key['account_id'] or grant['revoked_at'] is not None
                or grant['active_key_id'] != key_id or app['status'] == 'suspended'
                or (app['status'] != 'verified' and app['owner_account_id'] != key['account_id'])
                or 'models:invoke' not in grant['scope'].split()):
                raise BillingError('oauth_grant_disabled')
            owner_type, owner_id, limit = 'grant', grant['id'], grant['monthly_limit_microcredits']
            eligible = app['status'] == 'verified'
        old = (await c.execute(select(requests).where(requests.c.id == request_id))).mappings().first()
        if old:
            if old['payload_fingerprint'] != payload_hash:
                raise BillingError('request_reference_conflict', 409)
            return dict(old)
        await offset_idle_debt(c, key['account_id'], 'reserve:' + request_id)
        a, b = await state(c, key['account_id'])
        if a['debt_microcredits']:
            error = BillingError('debt_outstanding', 402)
        else:
            price = await read_price(c, model)
            amount = cost(input_bound, output_bound, price['input_rate_microcredits'], price['output_rate_microcredits'])
            count = await c.scalar(select(func.count()).select_from(requests).where(requests.c.account_id == key['account_id'], requests.c.status == 'reserved'))
            recent = await c.scalar(select(func.count()).select_from(requests).where(requests.c.account_id == key['account_id'], requests.c.created_at > now()-60))
            if recent >= 60 or count >= 8:
                raise BillingError('request_rate_limit' if recent >= 60 else 'concurrency_limit', 429)
            month = datetime.fromtimestamp(now(), timezone.utc).strftime('%Y-%m')
            match = (months.c.owner_type == owner_type, months.c.owner_id == owner_id, months.c.month == month)
            bucket = (await c.execute(select(months).where(*match).with_for_update())).mappings().first()
            if bucket is None:
                await c.execute(insert(months).values(owner_type=owner_type, owner_id=owner_id, month=month, created_at=now(), updated_at=now()))
                settled, reserved = 0, 0
            else:
                settled, reserved = bucket['settled_microcredits'], bucket['reserved_microcredits']
            if limit is not None and (integer(limit) == 0 or settled + reserved + amount > limit):
                raise BillingError('monthly_limit_exceeded', 402)
            welcome = min(amount, b['welcome']['balance_microcredits']-b['welcome']['reserved_microcredits']) if eligible else 0
            regular = amount-welcome
            if b['regular']['balance_microcredits']-b['regular']['reserved_microcredits'] < regular:
                raise BillingError('insufficient_balance', 402)
            b['regular']['reserved_microcredits'] += regular
            b['welcome']['reserved_microcredits'] += welcome
            await save(c, a, b)
            await c.execute(update(months).where(*match).values(reserved_microcredits=integer(reserved+amount), updated_at=now()))
            values = dict(id=request_id, account_id=key['account_id'], api_key_id=key_id, model=model,
                price_version=0, input_rate=0, output_rate=0, reserved=0, charged=0,
                protocol_version=2, price_version_v2=price['version'],
                input_rate_microcredits=price['input_rate_microcredits'], output_rate_microcredits=price['output_rate_microcredits'],
                reserved_microcredits=amount, status='reserved', month=month, month_owner_type=owner_type,
                month_owner_id=owner_id, regular_reserved_microcredits=regular, welcome_reserved_microcredits=welcome,
                input_estimate=input_bound, output_requested=output_bound, estimator_version=estimator_version,
                payload_fingerprint=payload_hash, debt_welcome_eligible=eligible, created_at=now(), updated_at=now())
            await c.execute(insert(requests).values(**values))
            return values
    if error:
        raise error


async def finish(c, r, tokens, cancelled=False, evidence=None):
    from .core import cost, now
    amount = 0 if cancelled else cost(*tokens, r['input_rate_microcredits'], r['output_rate_microcredits'])
    a, b = await state(c, r['account_id'])
    remaining = amount
    deductions = {'regular': 0, 'welcome': 0}
    # Release only this reservation. First consume its original bucket allocation.
    for kind in ('welcome', 'regular'):
        allocated = r[kind+'_reserved_microcredits']
        b[kind]['reserved_microcredits'] -= allocated
        take = min(remaining, allocated)
        deductions[kind] += take
        b[kind]['balance_microcredits'] -= take
        remaining -= take
    for kind in ('welcome', 'regular') if r['debt_welcome_eligible'] else ('regular',):
        take = min(remaining, b[kind]['balance_microcredits']-b[kind]['reserved_microcredits'])
        deductions[kind] += take
        b[kind]['balance_microcredits'] -= take
        remaining -= take
    a['debt_microcredits'] = integer(a['debt_microcredits'] + remaining)
    restricted = remaining if not r['debt_welcome_eligible'] else 0
    a['regular_only_debt_microcredits'] += restricted
    await save(c, a, b)
    await event(c, r['account_id'], 'request:'+r['id'], 'consume', amount=-(amount-remaining), debt=remaining,
                regular_debt=restricted, charged=amount, regular=-deductions['regular'], welcome=-deductions['welcome'], request_id=r['id'])
    await c.execute(update(months).where(months.c.owner_type == r['month_owner_type'], months.c.owner_id == r['month_owner_id'], months.c.month == r['month']).values(
        reserved_microcredits=months.c.reserved_microcredits-r['reserved_microcredits'], settled_microcredits=months.c.settled_microcredits+amount, updated_at=now()))
    await c.execute(update(requests).where(requests.c.id == r['id']).values(status='cancelled' if cancelled else 'settled',
        charged_microcredits=amount, input_tokens=tokens[0], output_tokens=tokens[1], evidence_json=evidence,
        resolved_at=now(), updated_at=now()))
    await offset_idle_debt(c, r['account_id'], 'settle:'+r['id'])


async def settle(engine, request_id, evidence=None):
    from .core import account_lock, now
    if evidence is None:
        evidence = UsageEvidence()
    if isinstance(evidence, dict):
        evidence = UsageEvidence(**evidence)
    async with engine.begin() as c:
        r = (await c.execute(select(requests).where(requests.c.id == request_id))).mappings().first()
        if r is None:
            raise BillingError('request_not_found', 404)
        await account_lock(c, r['account_id'])
        r = (await c.execute(select(requests).where(requests.c.id == request_id))).mappings().one()
        if r['status'] not in ('reserved', 'review'):
            return
        if r['protocol_version'] != 2:
            raise BillingError('incompatible_request_protocol', 503)
        tokens = evidence.tokens(r)
        if tokens is None:
            if r['status'] == 'review':
                return
            await c.execute(update(requests).where(requests.c.id == request_id).values(status='review', evidence_json=asdict(evidence), updated_at=now()))
            return
        await finish(c, r, tokens, cancelled=not evidence.sent_upstream, evidence=asdict(evidence))


async def resolve_review(engine, request_id, action, input_tokens=None, output_tokens=None, *, actor, reason, reference):
    from .core import account_lock, add_audit, now
    if not actor or not reason or action not in ('waive', 'charge'):
        raise BillingError('invalid_resolution', 400)
    if action == 'charge':
        integer(input_tokens); integer(output_tokens)
    elif input_tokens is not None or output_tokens is not None:
        raise BillingError('invalid_resolution', 400)
    decision = fingerprint([action, input_tokens, output_tokens, actor, reason, reference])
    async with engine.begin() as c:
        r = (await c.execute(select(requests).where(requests.c.id == request_id))).mappings().first()
        if r is None:
            raise BillingError('request_not_found', 404)
        await account_lock(c, r['account_id'])
        r = (await c.execute(select(requests).where(requests.c.id == request_id))).mappings().one()
        old = (await c.execute(select(resolutions).where(resolutions.c.request_id == request_id))).mappings().first()
        if old:
            if old['decision_hash'] != decision:
                raise BillingError('resolution_conflict', 409)
            return
        if r['status'] != 'review':
            raise BillingError('request_not_in_review', 409)
        await reference_lock(c, 'resolution:' + reference if len(reference) <= 89 else reference)
        if await c.scalar(select(resolutions.c.request_id).where(resolutions.c.reference == reference)):
            raise BillingError('resolution_reference_conflict', 409)
        await c.execute(insert(resolutions).values(request_id=request_id, action=action, input_tokens=input_tokens,
            output_tokens=output_tokens, actor=actor, reason=reason, reference=reference, decision_hash=decision, applied_at=now(), created_at=now()))
        await finish(c, r, (input_tokens or 0, output_tokens or 0), cancelled=action == 'waive')
        await add_audit(c, actor, 'resolve_'+action, request_id, reason)
