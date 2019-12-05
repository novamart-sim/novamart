"""Payment-gateway webhooks (refunds v2): the gateway is the source
of truth for money movements — we mirror them as payments rows."""
from fastapi import APIRouter

from .. import db
from ..logutil import app_log

router = APIRouter()


@router.post("/payments/gateway_refund")
async def gateway_refund(body: dict):
    ts = body["ts"]
    oid = int(body["order_id"])
    amount = float(body["amount"])
    async with db.pool.connection() as conn:
        await db.execute(conn, ts,
            "INSERT INTO payments(order_id, gross, fee, net, created_at) "
            "VALUES(%s,%s,%s,%s,%s)", (oid, -amount, 0.0, -amount, ts))
    app_log(ts, "INFO", "gateway_refund", order_id=oid, amount=amount)
    return {"ok": True}
