"""Order creation from payment-gateway callbacks."""
from time import perf_counter

from fastapi import APIRouter, HTTPException

from .. import db
from ..constants import FEE_FLAT, FEE_RATE, STATUS_CANCELLED, STATUS_REFUNDED
from ..logutil import app_log
from .catalog import ensure_entities

router = APIRouter()


@router.post("/orders")
async def create_order(body: dict):
    started = perf_counter()
    ts = body["ts"]
    price = body["price"]
    fee = round(price * FEE_RATE + FEE_FLAT, 2)
    created = False
    async with db.pool.connection() as conn:
        await db.execute(conn, ts,
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (body["ref"],))
        cur = await db.execute(conn, ts,
            "SELECT o.id, o.status, EXISTS(SELECT 1 FROM payments p WHERE p.order_id = o.id) AS has_payment "
            "FROM orders o WHERE payment_ref = %s ORDER BY id LIMIT 1",
            (body["ref"],))
        row = await cur.fetchone()
        if row:
            oid, status, has_payment = row
            if not has_payment:
                await db.execute(conn, ts,
                    "INSERT INTO payments(order_id, gross, fee, net, created_at) VALUES(%s,%s,%s,%s,%s)",
                    (oid, price, fee, round(price - fee, 2), ts))
            if status == 0:
                await db.execute(conn, ts,
                    "UPDATE orders SET status = 1, updated_at = %s WHERE id = %s", (ts, oid))
        else:
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
            created = True
    app_log(ts, "INFO", "order_created" if created else "order_callback_replayed",
            order_id=oid, user_id=body["uid"], product_id=body["pid"],
            price=price, payment_ref=body["ref"], session=body["session"],
            duration_ms=round((perf_counter() - started) * 1000, 1))
    return {"order_id": oid}


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: int, body: dict):
    ts = body["ts"]
    async with db.pool.connection() as conn:
        cur = await db.execute(conn, ts,
            "SELECT status FROM orders WHERE id = %s FOR UPDATE",
            (order_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="order not found")
        old_status = row[0]
        if old_status == STATUS_REFUNDED:
            raise HTTPException(status_code=409, detail="refunded orders cannot be cancelled")
        if old_status != STATUS_CANCELLED:
            await db.execute(conn, ts,
                "UPDATE orders SET status = %s, updated_at = %s WHERE id = %s",
                (STATUS_CANCELLED, ts, order_id))
    app_log(ts, "INFO", "order_cancelled", order_id=order_id,
            old_status=old_status, new_status=STATUS_CANCELLED)
    return {"ok": True, "order_id": order_id, "status": STATUS_CANCELLED}


@router.post("/orders/{order_id}/refund")
async def refund_order(order_id: int, body: dict):
    ts = body["ts"]
    async with db.pool.connection() as conn:
        cur = await db.execute(conn, ts,
            "SELECT status FROM orders WHERE id = %s FOR UPDATE",
            (order_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="order not found")
        old_status = row[0]
        if old_status not in (1, STATUS_REFUNDED):
            raise HTTPException(status_code=409, detail="only paid orders can be refunded")
        if old_status != STATUS_REFUNDED:
            await db.execute(conn, ts,
                "UPDATE orders SET status = %s, updated_at = %s WHERE id = %s",
                (STATUS_REFUNDED, ts, order_id))
    app_log(ts, "INFO", "order_refunded", order_id=order_id,
            old_status=old_status, new_status=STATUS_REFUNDED)
    return {"ok": True, "order_id": order_id, "status": STATUS_REFUNDED}
