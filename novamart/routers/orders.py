"""Order creation from payment-gateway callbacks."""
from fastapi import APIRouter

from .. import db
from ..constants import FEE_RATE
from ..logutil import app_log
from .catalog import ensure_entities

router = APIRouter()


@router.post("/orders")
async def create_order(body: dict):
    ts = body["ts"]
    price = body["price"]
    fee = round(price * FEE_RATE, 2)
    async with db.pool.connection() as conn:
        await ensure_entities(conn, ts, body["uid"], body["pid"], price)
        cur = await db.execute(conn, ts,
            "INSERT INTO orders(user_id, product_id, price, payment_ref, status, created_at, updated_at) "
            "VALUES(%s,%s,%s,%s,0,%s,%s) RETURNING id",
            (body["uid"], body["pid"], price, body["ref"], ts, ts))
        oid = (await cur.fetchone())[0]
        await db.execute(conn, ts,
            "INSERT INTO payments(order_id, gross, fee, net, created_at) VALUES(%s,%s,%s,%s,%s)",
            (oid, price, fee, round(price - fee, 2), ts))
        await db.execute(conn, ts,
            "UPDATE orders SET status = 1, updated_at = %s WHERE id = %s", (ts, oid))
    app_log(ts, "INFO", "order_created", order_id=oid, user_id=body["uid"],
            product_id=body["pid"], price=price, payment_ref=body["ref"], session=body["session"])
    return {"order_id": oid}
