"""Cart events."""
from fastapi import APIRouter

from .. import db
from ..logutil import app_log
from .catalog import ensure_entities

router = APIRouter()


@router.post("/cart")
async def add_to_cart(body: dict):
    ts = body["ts"]
    async with db.pool.connection() as conn:
        await ensure_entities(conn, ts, body["uid"], body["pid"], body.get("price", 0.0))
        await db.execute(conn, ts,
                         "INSERT INTO cart_items(user_id, product_id, session, created_at) VALUES(%s,%s,%s,%s)",
                         (body["uid"], body["pid"], body["session"], ts))
    app_log(ts, "INFO", "cart_item_added", user_id=body["uid"], product_id=body["pid"], session=body["session"])
    return {"ok": True}


@router.post("/cart/remove")
async def remove_from_cart(body: dict):
    ts = body["ts"]
    async with db.pool.connection() as conn:
        await db.execute(conn, ts,
                         "DELETE FROM cart_items WHERE user_id=%s AND product_id=%s AND session=%s",
                         (body["uid"], body["pid"], body["session"]))
    app_log(ts, "INFO", "cart_item_removed", user_id=body["uid"], product_id=body["pid"], session=body["session"])
    return {"ok": True}
