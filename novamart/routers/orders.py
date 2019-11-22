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
    appended = False
    order_total = price
    async with db.pool.connection() as conn:
        await db.execute(conn, ts,
            "CREATE TABLE IF NOT EXISTS order_lines ("
            "order_id BIGINT NOT NULL, product_id BIGINT NOT NULL, price NUMERIC NOT NULL, "
            "session TEXT NOT NULL, payment_ref TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL)")
        await db.execute(conn, ts,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_order_lines_payment_ref ON order_lines(payment_ref)")
        await db.execute(conn, ts,
            "CREATE INDEX IF NOT EXISTS idx_order_lines_session_created ON order_lines(session, created_at DESC)")
        await db.execute(conn, ts,
            "ALTER TABLE payments ADD COLUMN IF NOT EXISTS payment_ref TEXT")
        await db.execute(conn, ts,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_payment_ref ON payments(payment_ref) "
            "WHERE payment_ref IS NOT NULL")
        await db.execute(conn, ts,
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (body["session"],))
        await db.execute(conn, ts,
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (body["ref"],))
        cur = await db.execute(conn, ts,
            "SELECT oid, status, has_payment FROM ("
            "SELECT o.id AS oid, o.status, "
            "EXISTS(SELECT 1 FROM payments p WHERE p.order_id = o.id "
            "AND (p.payment_ref = %s OR (p.payment_ref IS NULL AND o.payment_ref = %s))) AS has_payment "
            "FROM orders o WHERE o.payment_ref = %s "
            "UNION ALL "
            "SELECT o.id AS oid, o.status, "
            "EXISTS(SELECT 1 FROM payments p WHERE p.order_id = o.id AND p.payment_ref = %s) AS has_payment "
            "FROM order_lines ol JOIN orders o ON o.id = ol.order_id WHERE ol.payment_ref = %s"
            ") refs ORDER BY oid LIMIT 1",
            (body["ref"], body["ref"], body["ref"], body["ref"], body["ref"]))
        row = await cur.fetchone()
        if row:
            oid, status, has_payment = row
            if not has_payment:
                await db.execute(conn, ts,
                    "INSERT INTO payments(order_id, gross, fee, net, payment_ref, created_at) VALUES(%s,%s,%s,%s,%s,%s)",
                    (oid, price, fee, round(price - fee, 2), body["ref"], ts))
            if status == 0:
                await db.execute(conn, ts,
                    "UPDATE orders SET status = 1, updated_at = %s WHERE id = %s", (ts, oid))
        else:
            await ensure_entities(conn, ts, body["uid"], body["pid"], price)
            cur = await db.execute(conn, ts,
                "SELECT o.id FROM orders o "
                "JOIN order_lines ol ON ol.order_id = o.id "
                "WHERE o.user_id = %s AND ol.session = %s "
                "AND ol.created_at >= (%s::timestamptz - INTERVAL '15 minutes') AND ol.created_at <= %s "
                "AND o.status NOT IN (%s, %s) "
                "ORDER BY ol.created_at DESC, o.id DESC LIMIT 1",
                (body["uid"], body["session"], ts, ts, STATUS_CANCELLED, STATUS_REFUNDED))
            row = await cur.fetchone()
            if row:
                oid = row[0]
                cur = await db.execute(conn, ts,
                    "UPDATE orders SET price = price + %s, status = 1, updated_at = %s WHERE id = %s RETURNING price",
                    (price, ts, oid))
                order_total = (await cur.fetchone())[0]
                await db.execute(conn, ts,
                    "INSERT INTO order_lines(order_id, product_id, price, session, payment_ref, created_at) "
                    "VALUES(%s,%s,%s,%s,%s,%s)",
                    (oid, body["pid"], price, body["session"], body["ref"], ts))
                await db.execute(conn, ts,
                    "INSERT INTO payments(order_id, gross, fee, net, payment_ref, created_at) VALUES(%s,%s,%s,%s,%s,%s)",
                    (oid, price, fee, round(price - fee, 2), body["ref"], ts))
                appended = True
            else:
                cur = await db.execute(conn, ts,
                    "INSERT INTO orders(user_id, product_id, price, payment_ref, status, created_at, updated_at) "
                    "VALUES(%s,%s,%s,%s,0,%s,%s) RETURNING id",
                    (body["uid"], body["pid"], price, body["ref"], ts, ts))
                oid = (await cur.fetchone())[0]
                await db.execute(conn, ts,
                    "INSERT INTO order_lines(order_id, product_id, price, session, payment_ref, created_at) "
                    "VALUES(%s,%s,%s,%s,%s,%s)",
                    (oid, body["pid"], price, body["session"], body["ref"], ts))
                await db.execute(conn, ts,
                    "INSERT INTO payments(order_id, gross, fee, net, payment_ref, created_at) VALUES(%s,%s,%s,%s,%s,%s)",
                    (oid, price, fee, round(price - fee, 2), body["ref"], ts))
                await db.execute(conn, ts,
                    "UPDATE orders SET status = 1, updated_at = %s WHERE id = %s", (ts, oid))
                created = True
    app_log(ts, "INFO",
            "order_created" if created else "order_appended" if appended else "order_callback_replayed",
            order_id=oid, user_id=body["uid"], product_id=body["pid"],
            price=price, order_total=round(float(order_total), 2), payment_ref=body["ref"], session=body["session"],
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
