"""Account creation."""
from uuid import uuid4

from fastapi import APIRouter

from .. import db
from ..logutil import app_log
from ..onboarding import user_profile

router = APIRouter()

USER_INSERT = ("INSERT INTO users(id, email, name, region, signup_channel, device, "
               "age_band, marketing_opt_in, created_at) "
               "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING")


def _user_row(uid, ts):
    p = user_profile(uid)
    return (uid, f"user{uid}@example.com", p["name"], p["region"], p["signup_channel"],
            p["device"], p["age_band"], p["marketing_opt_in"], ts)


@router.post("/accounts")
async def create_account(body: dict):
    ts = body["ts"]
    uid = body["uid"]
    account_id = uuid4()
    async with db.pool.connection() as conn:
        await db.execute(conn, ts,
                         "CREATE TABLE IF NOT EXISTS accounts ("
                         "account_id UUID PRIMARY KEY, email TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL)")
        await db.execute(conn, ts,
                         "CREATE TABLE IF NOT EXISTS account_map ("
                         "uid BIGINT NOT NULL, account_id UUID NOT NULL REFERENCES accounts(account_id), "
                         "linked_at TIMESTAMPTZ NOT NULL)")
        await db.execute(conn, ts, USER_INSERT, _user_row(uid, ts))
        cur = await db.execute(conn, ts,
                               "SELECT email FROM users WHERE id = %s",
                               (uid,))
        email = (await cur.fetchone())[0]
        await db.execute(conn, ts,
                         "INSERT INTO accounts(account_id, email, created_at) VALUES(%s,%s,%s)",
                         (account_id, email, ts))
        await db.execute(conn, ts,
                         "INSERT INTO account_map(uid, account_id, linked_at) VALUES(%s,%s,%s)",
                         (uid, account_id, ts))
    app_log(ts, "INFO", "account_created", user_id=uid,
            account_id=str(account_id), email=email)
    return {"account_id": str(account_id), "uid": uid, "email": email}
