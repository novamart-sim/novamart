"""User profile updates."""
from fastapi import APIRouter, HTTPException

from .. import db
from ..logutil import app_log

router = APIRouter()


@router.post("/users/{user_id}/email")
async def update_email(user_id: int, body: dict):
    ts = body["ts"]
    email = body["email"]
    async with db.pool.connection() as conn:
        cur = await db.execute(conn, ts,
                               "SELECT email FROM users WHERE id = %s FOR UPDATE",
                               (user_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="user not found")
        old_email = row[0]
        if old_email != email:
            await db.execute(conn, ts,
                             "UPDATE users SET email = %s WHERE id = %s",
                             (email, user_id))
    app_log(ts, "INFO", "user_email_updated", user_id=user_id,
            old_email=old_email, new_email=email)
    return {"ok": True, "user_id": user_id, "email": email}
