"""Explicit additive v1 -> v2 migration. No financial history is replayed."""
import hashlib
import json
from sqlalchemy import inspect, select, insert, update, text, func
from sqlalchemy.schema import CreateColumn, CreateTable, CreateIndex, AddConstraint
from .schema import metadata, version, accounts, buckets, keys, requests, ledger, settings, prices, price_configs, migrations, migration_snapshots
from .validation import BillingError, integer

DEFAULTS = {
    'pricing.global_margin_bps': 3000,
    'purchase.usd_cny_rate': {'numerator': 7, 'denominator': 1},
    'purchase.credits_per_cny': {'numerator': 10, 'denominator': 1},
    'purchase.packages': [dict(id='usd'+str(c//100), amount_usd_cents=c, bonus_bps=b) for c, b in [(1000, 0), (5000, 500), (10000, 800), (50000, 1200)]],
    'identity.welcome_microcredits': '100000000',
}


async def defaults(c):
    from .core import now
    for key, value in DEFAULTS.items():
        if not await c.scalar(select(settings.c.key).where(settings.c.key == key)):
            await c.execute(insert(settings).values(key=key, value_json=value, version=1, updated_by='system:migration', created_at=now(), updated_at=now()))


async def lock(c):
    if c.dialect.name == 'postgresql':
        await c.execute(text('SELECT pg_advisory_xact_lock(85273419)'))


async def initialize(engine):
    """Install a fresh database; existing v1 databases require explicit upgrade."""
    async with engine.begin() as c:
        await lock(c)
        names = await c.run_sync(lambda sync: inspect(sync).get_table_names())
        if 'billing_schema' in names:
            current = await c.scalar(text('SELECT version FROM billing_schema WHERE id=1'))
            if current != 2:
                raise BillingError('explicit_v2_migration_required', 503)
            return
        await c.run_sync(metadata.create_all)
        await c.execute(insert(version).values(id=1, version=2, protocol_version=2, unit='microcredit'))
        await defaults(c)


async def upgrade(engine, *, apply=False, migration_id='shared-v1-v2', backup_ref=None):
    from .core import now
    from .funds import event
    from .pricing import sync_price
    if not migration_id or len(migration_id) > 64:
        raise BillingError('invalid_migration_id', 400)
    async with engine.begin() as c:
        await lock(c)
        current = await c.scalar(text('SELECT version FROM billing_schema WHERE id=1'))
        if current == 2:
            return {'version': 2, 'already_applied': True}
        if current != 1:
            raise BillingError('incompatible_billing_schema', 503)
        # Read v1 via raw mappings: v2 columns do not exist yet.
        old = {}
        for name in ('billing_accounts', 'billing_keys', 'billing_prices', 'billing_requests', 'billing_ledger', 'billing_resolutions'):
            old[name] = [dict(r) for r in (await c.execute(text('SELECT * FROM '+name))).mappings()]
        if any(r['status'] in ('reserved', 'review') for r in old['billing_requests']):
            raise BillingError('migration_requests_not_drained', 409)
        names = await c.run_sync(lambda sync: inspect(sync).get_table_names())
        for table, predicate in [('portal_refunds', "status NOT IN ('completed','cancelled','failed')"), ('portal_orders', "status IN ('pending','created')")]:
            if table in names and await c.scalar(text('SELECT count(*) FROM '+table+' WHERE '+predicate)):
                raise BillingError('migration_portal_not_drained', 409)
        for a in old['billing_accounts']:
            integer(a['balance']*10); integer(a['reserved']*10)
            if a['reserved'] != 0:
                raise BillingError('migration_reservations_not_drained', 409)
            total = sum(r['amount'] for r in old['billing_ledger'] if r['account_id'] == a['id'])
            if total != a['balance']:
                raise BillingError('migration_ledger_unreconciled', 409)
        seen = set()
        for k in old['billing_keys']:
            pair = (k['account_id'], k['name'])
            if not k['revoked'] and pair in seen:
                raise BillingError('migration_duplicate_key_names', 409)
            if not k['revoked']:
                seen.add(pair)
        for r in old['billing_requests']:
            for field in ('reserved', 'charged', 'input_rate', 'output_rate'):
                integer(r[field]*10)
        for r in old['billing_ledger']:
            integer(r['amount']*10, minimum=-(2**63-1))
        checksum = {name: hashlib.sha256(json.dumps(sorted(rows, key=lambda r: json.dumps(r, sort_keys=True, default=str)), sort_keys=True, default=str).encode()).hexdigest() for name, rows in old.items()}
        if not apply:
            return {'version': 1, 'checksum': checksum, 'accounts': len(old['billing_accounts'])}
        if not backup_ref:
            raise BillingError('migration_backup_required', 400)
        # Compile explicit DDL for each missing table/column, never create_all on upgrade.
        for table in metadata.sorted_tables:
            if table.name not in names:
                await c.execute(CreateTable(table))
            else:
                columns = await c.run_sync(lambda sync, name=table.name: {col['name'] for col in inspect(sync).get_columns(name)})
                for column in table.columns:
                    if column.name not in columns:
                        await c.execute(text('ALTER TABLE '+table.name+' ADD COLUMN '+str(CreateColumn(column).compile(dialect=c.dialect))))
        for table in metadata.tables.values():
            existing = await c.run_sync(lambda sync, name=table.name: {i['name'] for i in inspect(sync).get_indexes(name)})
            for index in table.indexes:
                if index.name not in existing:
                    await c.execute(CreateIndex(index))
        if c.dialect.name == 'postgresql':
            # Existing v1 tables did not have v2 invariants. New tables already
            # received their constraints through CREATE TABLE above.
            from sqlalchemy import CheckConstraint, ForeignKeyConstraint
            for table in (accounts, keys, requests, ledger):
                for constraint in table.constraints:
                    if isinstance(constraint, ForeignKeyConstraint) or (isinstance(constraint, CheckConstraint) and str(constraint.sqltext) != 'reserved >= 0'):
                        await c.execute(AddConstraint(constraint))
        await c.execute(insert(migrations).values(id=migration_id, from_version=1, to_version=2, phase='applying', started_at=now(), checksum_json=checksum, backup_ref=backup_ref))
        for name, rows in old.items():
            for row in rows:
                row_id = str(row.get('id', row.get('api_key_id', row.get('model', row.get('request_id')))))
                await c.execute(insert(migration_snapshots).values(migration_id=migration_id, table_name=name, row_id=row_id, row_json=row))
        for a in old['billing_accounts']:
            await c.execute(update(accounts).where(accounts.c.id == a['id']).values(balance_microcredits=a['balance']*10, reserved_microcredits=0))
            for kind in ('regular', 'welcome'):
                await c.execute(insert(buckets).values(account_id=a['id'], kind=kind, balance_microcredits=a['balance']*10 if kind == 'regular' else 0))
            await event(c, a['id'], 'migration:'+hashlib.sha256((migration_id+':'+a['id']).encode()).hexdigest(), 'migration', metadata={'old_unit': 'microcny', 'new_unit': 'microcredit', 'old_balance': a['balance'], 'new_balance': a['balance']*10, 'checksum': checksum})
        for r in old['billing_requests']:
            await c.execute(update(requests).where(requests.c.id == r['id']).values(protocol_version=1,
                **{f+'_microcredits': r[f]*10 for f in ('reserved', 'charged', 'input_rate', 'output_rate')}))
        for r in old['billing_ledger']:
            await c.execute(update(ledger).where(ledger.c.id == r['id']).values(protocol_version=1, reference=r['id'], amount_microcredits=r['amount']*10))
        await defaults(c)
        for p in old['billing_prices']:
            await c.execute(insert(price_configs).values(model=p['model'], sales_enabled=p['enabled']))
            await sync_price(c, p['model'])
        # Conservation checks run before the protocol pointer becomes writable by v2.
        total = await c.scalar(select(func.sum(accounts.c.balance_microcredits))) or 0
        bucket_total = await c.scalar(select(func.sum(buckets.c.balance_microcredits))) or 0
        if total != bucket_total or total != sum(a['balance']*10 for a in old['billing_accounts']):
            raise BillingError('migration_conservation_failed', 409)
        await c.execute(update(migrations).where(migrations.c.id == migration_id).values(phase='complete', finished_at=now()))
        await c.execute(update(version).where(version.c.id == 1).values(version=2, protocol_version=2, unit='microcredit', migration_id=migration_id))
        return {'version': 2, 'checksum': checksum, 'accounts': len(old['billing_accounts'])}
