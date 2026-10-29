"""Account-locked bucket movements and append-only financial events."""
import hashlib
from sqlalchemy import select, insert, update, text
from .schema import accounts, buckets, ledger
from .validation import integer, BillingError


async def state(c, account_id):
    a = dict((await c.execute(select(accounts).where(accounts.c.id == account_id))).mappings().one())
    rows = (await c.execute(select(buckets).where(buckets.c.account_id == account_id))).mappings().all()
    b = {r['kind']: dict(r) for r in rows}
    if set(b) != {'regular', 'welcome'}:
        raise BillingError('missing_credit_buckets', 503)
    return a, b


async def save(c, a, b):
    from .core import now
    for row in b.values():
        integer(row['balance_microcredits']); integer(row['reserved_microcredits'])
        await c.execute(update(buckets).where(buckets.c.account_id == a['id'], buckets.c.kind == row['kind']).values(
            balance_microcredits=row['balance_microcredits'], reserved_microcredits=row['reserved_microcredits'], updated_at=now()))
    values = {field: integer(a[field]) for field in ('debt_microcredits', 'regular_only_debt_microcredits')}
    values['chargeback_frozen'] = a['chargeback_frozen'] and values['regular_only_debt_microcredits'] > 0
    values.update(balance_microcredits=integer(sum(r['balance_microcredits'] for r in b.values())),
                  reserved_microcredits=integer(sum(r['reserved_microcredits'] for r in b.values())),
                  row_version=accounts.c.row_version+1)
    await c.execute(update(accounts).where(accounts.c.id == a['id']).values(**values))


async def reference_lock(c, reference):
    if not isinstance(reference, str) or not 1 <= len(reference) <= 100:
        raise BillingError('invalid_reference', 400)
    if c.dialect.name == 'postgresql':
        lock_id = int.from_bytes(hashlib.sha256(reference.encode()).digest()[:8], 'big', signed=True)
        await c.execute(text('SELECT pg_advisory_xact_lock(:id)'), {'id': lock_id})


async def event(c, account_id, reference, kind, *, amount=0, debt=0, regular_debt=0, gross=0, charged=0, regular=0, welcome=0, request_id=None, metadata=None):
    from .core import now
    await reference_lock(c, reference)
    if await c.scalar(select(ledger.c.id).where(ledger.c.reference == reference)):
        raise BillingError('ledger_reference_conflict', 409)
    if not isinstance(reference, str) or not 1 <= len(reference) <= 100:
        raise BillingError('invalid_reference', 400)
    for value in (amount, debt, regular_debt, regular, welcome):
        integer(value, minimum=-(2**63-1))
    await c.execute(insert(ledger).values(id=reference, reference=reference, account_id=account_id,
        amount=0, protocol_version=2, kind=kind, amount_microcredits=amount,
        debt_delta_microcredits=debt, regular_only_debt_delta_microcredits=regular_debt,
        gross_microcredits=integer(gross), charged_microcredits=integer(charged),
        regular_delta_microcredits=regular, welcome_delta_microcredits=welcome,
        request_id=request_id, metadata_json=metadata or {}, created_at=now()))


async def offset_idle_debt(c, account_id, operation_reference):
    reference = 'debt-offset:' + hashlib.sha256(operation_reference.encode()).hexdigest()
    if await c.scalar(select(ledger.c.id).where(ledger.c.reference == reference)):
        return
    a, b = await state(c, account_id)
    ordinary = a['debt_microcredits'] - a['regular_only_debt_microcredits']
    welcome = min(ordinary, b['welcome']['balance_microcredits']-b['welcome']['reserved_microcredits'])
    regular = min(a['debt_microcredits']-welcome, b['regular']['balance_microcredits']-b['regular']['reserved_microcredits'])
    restricted = min(a['regular_only_debt_microcredits'], regular)
    if not welcome + regular:
        return
    b['welcome']['balance_microcredits'] -= welcome
    b['regular']['balance_microcredits'] -= regular
    a['debt_microcredits'] -= welcome+regular
    a['regular_only_debt_microcredits'] -= restricted
    await save(c, a, b)
    await event(c, account_id, reference, 'debt_offset', amount=-welcome-regular,
                debt=-welcome-regular, regular_debt=-restricted, regular=-regular, welcome=-welcome)


async def credit_in_transaction(c, account_id, amount, reference, kind='credit', eligibility='regular'):
    from .core import account_lock
    integer(amount, minimum=1)
    if not isinstance(kind, str) or not 1 <= len(kind) <= 24:
        raise BillingError('invalid_credit_kind', 400)
    if eligibility not in ('regular', 'welcome'):
        raise BillingError('invalid_credit_eligibility', 400)
    await account_lock(c, account_id)
    await reference_lock(c, reference)
    old = (await c.execute(select(ledger).where(ledger.c.reference == reference))).mappings().first()
    if old:
        if (old['account_id'], old['gross_microcredits'], old['kind'], (old['metadata_json'] or {}).get('eligibility')) != (account_id, amount, kind, eligibility):
            raise BillingError('credit_reference_conflict', 409)
        return
    a, b = await state(c, account_id)
    eligible = a['debt_microcredits'] if eligibility == 'regular' else a['debt_microcredits']-a['regular_only_debt_microcredits']
    offset = min(amount, eligible)
    restricted = min(offset, a['regular_only_debt_microcredits']) if eligibility == 'regular' else 0
    a['debt_microcredits'] -= offset
    a['regular_only_debt_microcredits'] -= restricted
    b[eligibility]['balance_microcredits'] += amount-offset
    await save(c, a, b)
    await event(c, account_id, reference, kind, amount=amount-offset, debt=-offset,
        regular_debt=-restricted, gross=amount, regular=amount-offset if eligibility == 'regular' else 0,
        welcome=amount-offset if eligibility == 'welcome' else 0, metadata={'eligibility': eligibility})
    await offset_idle_debt(c, account_id, reference)
