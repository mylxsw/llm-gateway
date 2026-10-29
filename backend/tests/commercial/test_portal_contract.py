"""Portal composition shares the gateway's validation and transaction boundary."""
import pytest
from sqlalchemy import select
from squirrel_commercial import core
from squirrel_commercial.schema import audit, keys
from squirrel_commercial.pricing import quote_order


@pytest.mark.parametrize('actor,kind', [('admin:operator-1','admin'), ('system:sync','system'), ('gateway-admin','gateway_admin'), ('customer-1','user')])
async def test_audit_actor_identity(billing, actor, kind):
    async with billing.begin() as c:
        await core.add_audit(c, actor, 'test', 'target', 'test reason')
    async with billing.connect() as c:
        row = (await c.execute(select(audit).where(audit.c.action == 'test'))).mappings().one()
        assert row['actor_type'] == kind and row['actor_id'] == actor


async def test_key_changes_compose_and_rollback(billing):
    kid, _ = await core.create_key(billing, 'alice', 'composed', monthly_limit_microcredits=100)
    with pytest.raises(RuntimeError):
        async with billing.begin() as c:
            await core.set_key_monthly_limit_in_transaction(c, 'alice', kid, 200)
            await core.user_key_action_in_transaction(c, 'alice', kid, 'pause')
            await core.admin_key_action_in_transaction(c, kid, {'key_name': 'renamed'}, actor='alice')
            raise RuntimeError('transaction aborted')
    async with billing.connect() as c:
        row = (await c.execute(select(keys).where(keys.c.api_key_id == kid))).mappings().one()
        assert row['monthly_limit_microcredits'] == 100 and not row['paused'] and row['name'] == 'composed'
    async with billing.begin() as c:
        await core.set_key_monthly_limit_in_transaction(c, 'alice', kid, None)
        await core.user_key_action_in_transaction(c, 'alice', kid, 'pause')
    async with billing.connect() as c:
        row = (await c.execute(select(keys).where(keys.c.api_key_id == kid))).mappings().one()
        assert row['monthly_limit_microcredits'] is None and row['paused']


def test_order_quote_rationals_and_integer_bounds():
    fx = {'usd_cny': {'numerator': 7, 'denominator': 1}, 'credits_per_cny': {'numerator': 10, 'denominator': 1}}
    assert quote_order({'amount_usd_cents': 5000, 'bonus_bps': 500}, fx) == (35000, 3500000000, 175000000)
    with pytest.raises(core.BillingError):
        quote_order({'amount_usd_cents': True, 'bonus_bps': 0}, fx)
    with pytest.raises(core.BillingError):
        quote_order({'amount_usd_cents': 2**63-1, 'bonus_bps': 10000}, fx)
    with pytest.raises(core.BillingError):
        quote_order({'amount_usd_cents': 10, 'bonus_bps': 0}, {**fx, 'usd_cny': {'numerator': 1, 'denominator': 0}})


async def test_review_decision_composes_and_rolls_back(billing):
    from squirrel_commercial.schema import requests, resolutions
    kid, _ = await core.create_key(billing, 'alice', 'review-composed')
    await core.reserve(billing, 'composed-review', kid, 'model', 10, 10)
    await core.settle(billing, 'composed-review')
    with pytest.raises(RuntimeError):
        async with billing.begin() as c:
            await core.resolve_review_in_transaction(c, 'composed-review', 'waive', actor='admin:operator', reason='checked', reference='composed-decision')
            raise RuntimeError('abort')
    async with billing.connect() as c:
        assert await c.scalar(select(requests.c.status).where(requests.c.id == 'composed-review')) == 'review'
        assert await c.scalar(select(resolutions.c.request_id).where(resolutions.c.request_id == 'composed-review')) is None
    await core.resolve_review(billing, 'composed-review', 'waive', actor='admin:operator', reason='checked', reference='composed-decision')
