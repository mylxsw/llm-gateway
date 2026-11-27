"""OAuth grant transactions and live gateway reservation checks."""

import asyncio

import pytest
from sqlalchemy import func, insert, select, update

from squirrel_commercial import core
from squirrel_commercial.oauth import (
    change_grant_in_transaction,
    issue_key_in_transaction,
)
from squirrel_commercial.schema import keys, oauth_apps, oauth_grants


async def app_lock(c):
    return (
        (
            await c.execute(
                select(oauth_apps).where(oauth_apps.c.id == "app").with_for_update()
            )
        )
        .mappings()
        .one()
    )


@pytest.fixture
async def oauth_app(billing):
    async with billing.begin() as c:
        await c.execute(
            insert(oauth_apps).values(
                id="app",
                owner_account_id="alice",
                client_id="client",
                name="Application",
                domain="app.example",
                client_type="public",
                status="verified",
            )
        )
    return billing


async def issue(engine, user="alice", limit=1000000):
    async with engine.begin() as c:
        app = await app_lock(c)
        return await issue_key_in_transaction(
            c, user, app, "models:invoke credits:read", limit
        )


async def grant(engine, user="alice"):
    async with engine.connect() as c:
        return (
            (
                await c.execute(
                    select(oauth_grants).where(oauth_grants.c.account_id == user)
                )
            )
            .mappings()
            .one()
        )


async def test_suspend_and_restore_at_gateway_reservation(oauth_app):
    engine = oauth_app
    await issue(engine)
    g = await grant(engine)
    await core.reserve(engine, "before", g["active_key_id"], "model", 1, 1)
    async with engine.begin() as c:
        await app_lock(c)
        await c.execute(update(oauth_apps).values(status="suspended"))
    with pytest.raises(core.BillingError, match="application_suspended"):
        await core.reserve(engine, "after", g["active_key_id"], "model", 1, 1)
    await core.settle(
        engine,
        "before",
        core.UsageEvidence(
            input_tokens=1,
            output_tokens=1,
            source="upstream",
            terminal_complete=True,
            sent_upstream=True,
        ),
    )
    async with engine.begin() as c:
        await app_lock(c)
        await c.execute(update(oauth_apps).values(status="verified"))
    await core.reserve(engine, "restored", g["active_key_id"], "model", 1, 1)


async def test_rotation_revoke_and_month_limit(oauth_app):
    engine = oauth_app
    first = await issue(engine)
    g = await grant(engine)
    second = await issue(engine)
    assert first != second and second.startswith("sqb-oa_")
    new = await grant(engine)
    assert new["id"] == g["id"] and new["active_key_id"] != g["active_key_id"]
    with pytest.raises(core.BillingError, match="commercial_key_disabled"):
        await core.reserve(engine, "old", g["active_key_id"], "model", 1, 1)
    async with engine.begin() as c:
        await app_lock(c)
        await change_grant_in_transaction(
            c, g["id"], "alice", monthly_limit=0, expected_revision=2
        )
    with pytest.raises(core.BillingError, match="monthly_limit_exceeded"):
        await core.reserve(engine, "limit", new["active_key_id"], "model", 1, 1)
    for _ in range(2):
        async with engine.begin() as c:
            await app_lock(c)
            await change_grant_in_transaction(c, g["id"], "alice", revoke=True)
    with pytest.raises(core.BillingError, match="commercial_key_disabled"):
        await core.reserve(engine, "revoked", new["active_key_id"], "model", 1, 1)
    with pytest.raises(core.BillingError, match="grant_revoked"):
        async with engine.begin() as c:
            await app_lock(c)
            await change_grant_in_transaction(c, g["id"], "alice", monthly_limit=None)


async def test_shared_mutation_validation_and_rollback(oauth_app):
    engine = oauth_app
    for limit in [1, 10**15 + 1000000, -1, True]:
        with pytest.raises(core.BillingError):
            await issue(engine, limit=limit)
    with pytest.raises(RuntimeError):
        async with engine.begin() as c:
            app = await app_lock(c)
            await issue_key_in_transaction(c, "alice", app, "models:invoke", None)
            raise RuntimeError("rollback")
    async with engine.connect() as c:
        assert await c.scalar(select(func.count()).select_from(oauth_grants)) == 0
        assert await c.scalar(select(func.count()).select_from(keys)) == 0
    await issue(engine)
    g = await grant(engine)
    for grant_id, owner, kwargs, error in [
        ("missing", "alice", {}, "not_found"),
        (g["id"], "bob", {}, "not_found"),
        (g["id"], "alice", dict(expected_revision=999), "version_conflict"),
        (g["id"], "alice", dict(monthly_limit=1), "invalid_amount"),
    ]:
        with pytest.raises(core.BillingError, match=error):
            async with engine.begin() as c:
                await app_lock(c)
                await change_grant_in_transaction(c, grant_id, owner, **kwargs)


async def test_parallel_grant_creation(oauth_app):
    engine = oauth_app
    await asyncio.gather(*[issue(engine) for _ in range(5)])
    async with engine.connect() as c:
        assert await c.scalar(select(func.count()).select_from(oauth_grants)) == 1
        assert (
            await c.scalar(
                select(func.count()).select_from(keys).where(keys.c.revoked.is_(False))
            )
            == 1
        )


async def test_editing_verified_app_blocks_existing_third_party(oauth_app):
    engine = oauth_app
    await issue(engine, "bob")
    g = await grant(engine, "bob")
    async with engine.begin() as c:
        await app_lock(c)
        await c.execute(update(oauth_apps).values(status="draft"))
    with pytest.raises(core.BillingError, match="oauth_grant_disabled"):
        await core.reserve(engine, "needs-review", g["active_key_id"], "model", 1, 1)
