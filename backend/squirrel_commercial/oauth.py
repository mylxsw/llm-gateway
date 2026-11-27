"""Composable OAuth grant mutations. Caller owns the transaction and app lock.

Lock order is app, account, grant, code. Month buckets survive key rotation.
"""

import secrets
import uuid

from sqlalchemy import insert, select, text, update

from . import core
from .schema import keys, oauth_grants


async def issue_key_in_transaction(c, account_id, app, scope, monthly_limit):
    if monthly_limit is not None:
        core.integer(monthly_limit)
        if monthly_limit % 1000000 or monthly_limit > 10**15:
            raise core.BillingError("invalid_amount", 400)
    account = await core.account_lock(c, account_id)
    if account["blocked"] or account["chargeback_frozen"]:
        raise core.BillingError("account_blocked", 403)
    grant = (
        (
            await c.execute(
                select(oauth_grants)
                .where(
                    oauth_grants.c.account_id == account_id,
                    oauth_grants.c.app_id == app["id"],
                )
                .with_for_update()
            )
        )
        .mappings()
        .first()
    )
    grant_id = grant["id"] if grant else str(uuid.uuid4())
    if grant and grant["active_key_id"]:
        await c.execute(
            update(keys)
            .where(keys.c.api_key_id == grant["active_key_id"])
            .values(revoked=True, revoked_at=core.now())
        )
    token = "sqb-oa_" + secrets.token_urlsafe(32)
    key_id = (
        await c.execute(
            text(
                "INSERT INTO api_keys (key_name,key_value,is_active,record_details,is_mcp_admin,created_at) "
                "VALUES (:name,:value,true,false,false,CURRENT_TIMESTAMP) RETURNING id"
            ),
            {"name": "oauth-" + str(uuid.uuid4()), "value": core.digest(token)},
        )
    ).scalar_one()
    await c.execute(
        insert(keys).values(
            api_key_id=key_id,
            account_id=account_id,
            name="oauth:" + grant_id,
            prefix=token[:12],
            source="oauth",
            oauth_grant_id=grant_id,
            paused=False,
            revoked=False,
            created_at=core.now(),
        )
    )
    values = dict(
        active_key_id=key_id,
        scope=scope,
        monthly_limit_microcredits=monthly_limit,
        revoked_at=None,
        updated_at=core.now(),
    )
    if grant:
        await c.execute(
            update(oauth_grants)
            .where(oauth_grants.c.id == grant_id)
            .values(**values, revision=grant["revision"] + 1)
        )
    else:
        await c.execute(
            insert(oauth_grants).values(
                **values,
                id=grant_id,
                account_id=account_id,
                app_id=app["id"],
                created_at=core.now(),
            )
        )
    await core.add_audit(
        c, account_id, "oauth_authorize", grant_id, "User authorized application"
    )
    return token


async def change_grant_in_transaction(
    c, grant_id, account_id, *, revoke=False, monthly_limit=None, expected_revision=None
):
    await core.account_lock(c, account_id)
    grant = (
        (
            await c.execute(
                select(oauth_grants)
                .where(
                    oauth_grants.c.id == grant_id,
                    oauth_grants.c.account_id == account_id,
                )
                .with_for_update()
            )
        )
        .mappings()
        .first()
    )
    if not grant:
        raise core.BillingError("not_found", 404)
    if expected_revision is not None and grant["revision"] != expected_revision:
        raise core.BillingError("version_conflict", 409)
    if grant["revoked_at"] is not None:
        if revoke:
            return
        raise core.BillingError("grant_revoked", 409)
    values = dict(revision=grant["revision"] + 1, updated_at=core.now())
    if revoke:
        values["revoked_at"] = core.now()
        await c.execute(
            update(keys)
            .where(keys.c.oauth_grant_id == grant_id)
            .values(revoked=True, revoked_at=core.now())
        )
    else:
        if monthly_limit is not None:
            core.integer(monthly_limit)
            if monthly_limit % 1000000 or monthly_limit > 10**15:
                raise core.BillingError("invalid_amount", 400)
        values["monthly_limit_microcredits"] = monthly_limit
    await c.execute(
        update(oauth_grants).where(oauth_grants.c.id == grant_id).values(**values)
    )
    await core.add_audit(
        c,
        account_id,
        "oauth_revoke" if revoke else "oauth_limit",
        grant_id,
        "User updated grant",
        after=values,
    )
