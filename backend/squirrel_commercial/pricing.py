"""Immutable price publication; reservation reads never acquire price locks."""
import hashlib
import json
from decimal import Decimal, ROUND_CEILING
from sqlalchemy import select, insert, update, text, Table, MetaData, Column, String, Numeric, Boolean
from .schema import settings, price_configs, price_versions, prices
from .validation import integer, BillingError

# A read-only projection avoids importing the gateway or its ORM into the package.
models = Table('model_mappings', MetaData(), Column('requested_model', String),
    Column('input_price', Numeric(12, 4)), Column('output_price', Numeric(12, 4)),
    Column('model_type', String), Column('alias_target_model', String),
    Column('billing_mode', String), Column('is_active', Boolean))


def quote_rate(base_nano_usd, margin_bps):
    integer(base_nano_usd)
    integer(margin_bps, maximum=100000)
    return integer(((base_nano_usd * 70 * (10000 + margin_bps) + 10**11-1) // 10**11) * 10000)


def nano(value):
    if value is None:
        return None
    value = Decimal(str(value))
    if not value.is_finite() or value < 0:
        return None
    return integer(int((value * 10**9).to_integral_value(rounding=ROUND_CEILING)))


def snapshot(model, config, global_margin):
    inp, out = nano(model['input_price']), nano(model['output_price'])
    margin = config['margin_bps'] if config['margin_bps'] is not None else global_margin
    integer(margin, maximum=100000)
    reason = next((why for condition, why in [
        (inp is None or out is None, 'missing_base_price'),
        (model['model_type'] != 'chat', 'unsupported_model_type'),
        (model['billing_mode'] != 'token_flat', 'unsupported_billing_mode'),
        (not config['sales_enabled'], 'sales_disabled'),
        (not model['is_active'], 'model_disabled')] if condition), None)
    values = dict(base_input_nano_usd=inp, base_output_nano_usd=out,
        margin_bps=margin, global_margin_bps=global_margin, inherits_global=config['margin_bps'] is None,
        pricing_factor=70, input_rate_microcredits=None if inp is None else quote_rate(inp, margin),
        output_rate_microcredits=None if out is None else quote_rate(out, margin),
        sales_enabled=config['sales_enabled'], model_enabled=model['is_active'], model_type=model['model_type'],
        alias_target_model=model['alias_target_model'], billing_mode=model['billing_mode'],
        sellable=reason is None, unavailable_reason=reason)
    values['source_fingerprint'] = hashlib.sha256(json.dumps([model['requested_model'], values], sort_keys=True).encode()).hexdigest()
    return values


async def sync_price(c, model, actor='system:price-sync', reason='Source synchronization'):
    from .core import now, add_audit
    # Global row serializes config creation and fixes the lock order on PG.
    global_margin = await c.scalar(select(settings.c.value_json).where(settings.c.key == 'pricing.global_margin_bps').with_for_update())
    row = (await c.execute(select(models).where(models.c.requested_model == model).with_for_update())).mappings().first()
    if row is None:
        return
    config = (await c.execute(select(price_configs).where(price_configs.c.model == model).with_for_update())).mappings().first()
    if config is None:
        await c.execute(insert(price_configs).values(model=model, sales_enabled=False, created_at=now(), updated_at=now()))
        config = dict(model=model, sales_enabled=False, margin_bps=None, current_version=None)
    values = snapshot(row, config, global_margin)
    old = (await c.execute(select(price_versions).where(price_versions.c.model == model, price_versions.c.version == config['current_version']))).mappings().first()
    if old and old['source_fingerprint'] == values['source_fingerprint']:
        return old
    number = (config['current_version'] or 0) + 1
    await c.execute(insert(price_versions).values(model=model, version=number, **values, actor=actor, reason=reason, created_at=now()))
    await c.execute(update(price_configs).where(price_configs.c.model == model).values(current_version=number, updated_at=now()))
    await add_audit(c, actor, 'price_publish', model, reason)
    return dict(model=model, version=number, **values)


async def read_price(c, model):
    # All source fields, current pointer and immutable version share one MVCC statement.
    stmt = select(models, price_configs.c.margin_bps.label('configured_margin'),
        price_configs.c.sales_enabled.label('configured_sales'), settings.c.value_json.label('global_margin'), price_versions).select_from(
        models.join(price_configs, price_configs.c.model == models.c.requested_model)
        .join(price_versions, (price_versions.c.model == price_configs.c.model) & (price_versions.c.version == price_configs.c.current_version))
        .join(settings, settings.c.key == 'pricing.global_margin_bps')).where(models.c.requested_model == model)
    row = (await c.execute(stmt)).mappings().first()
    if row is None:
        raise BillingError('price_sync_pending', 503)
    expected = snapshot(row, dict(margin_bps=row['configured_margin'], sales_enabled=row['configured_sales']), row['global_margin'])
    if row['source_fingerprint'] != expected['source_fingerprint']:
        raise BillingError('price_sync_pending', 503)
    if not row['sellable']:
        raise BillingError('model_not_for_sale')
    return row


async def configure_price(c, model, *, margin_bps=None, sales_enabled=False, actor, reason):
    from .core import now
    if margin_bps is not None:
        integer(margin_bps, maximum=100000)
    if type(sales_enabled) is not bool:
        raise BillingError('invalid_sales_enabled', 400)
    await c.execute(select(settings).where(settings.c.key == 'pricing.global_margin_bps').with_for_update())
    await sync_price(c, model, actor, reason)
    await c.execute(update(price_configs).where(price_configs.c.model == model).values(margin_bps=margin_bps, sales_enabled=sales_enabled, revision=price_configs.c.revision+1, updated_at=now()))
    return await sync_price(c, model, actor, reason)


async def set_global_margin(c, value, actor, reason):
    from .core import now
    integer(value, maximum=100000)
    await c.execute(update(settings).where(settings.c.key == 'pricing.global_margin_bps').values(value_json=value, version=settings.c.version+1, updated_by=actor, updated_at=now()))
    names = (await c.execute(select(models.c.requested_model).order_by(models.c.requested_model))).scalars().all()
    for name in names:
        await sync_price(c, name, actor, reason)
