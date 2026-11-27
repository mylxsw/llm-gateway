"""Credential-scoped credit snapshots using the reservation lock order."""
from datetime import datetime, timezone

from sqlalchemy import select, text

from . import core
from .funds import state
from .metering import oauth_lock
from .schema import months, oauth_grants


async def snapshot(engine, key_id):
    async with engine.begin() as c:
        key = await core.key_state(c, key_id, required_scope='credits:read')
        app = await oauth_lock(c, key)
        await core.account_lock(c, key['account_id'])
        key = await core.key_state(c, key_id, required_scope='credits:read')
        active = await c.scalar(text('SELECT is_active FROM api_keys WHERE id=:id'), {'id': key_id})
        if not active:
            raise core.BillingError('commercial_key_disabled')
        owner_type, owner_id = 'key', str(key_id)
        limit = key['monthly_limit_microcredits']
        if app:
            grant = (await c.execute(select(oauth_grants).where(
                oauth_grants.c.id == key['oauth_grant_id']))).mappings().one()
            owner_type, owner_id = 'grant', grant['id']
            limit = grant['monthly_limit_microcredits']
        account, buckets = await state(c, key['account_id'])
        eligible = buckets.values() if not app or app['status'] == 'verified' else [buckets['regular']]
        balance = sum(b['balance_microcredits'] for b in eligible)
        reserved = sum(b['reserved_microcredits'] for b in eligible)
        month = datetime.fromtimestamp(core.now(), timezone.utc).strftime('%Y-%m')
        usage = (await c.execute(select(months).where(
            months.c.owner_type == owner_type, months.c.owner_id == owner_id,
            months.c.month == month))).mappings().first()
        return {
            'balance': str(balance), 'reserved': str(reserved),
            'available': str(balance - reserved), 'debt': str(account['debt_microcredits']),
            'monthly_limit': str(limit) if limit is not None else None,
            'month_settled': str(usage['settled_microcredits'] if usage else 0),
            'month_reserved': str(usage['reserved_microcredits'] if usage else 0),
        }
