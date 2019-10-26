"""Similar-products widget: affinity top-K with bestseller fallback."""
from fastapi import APIRouter

from .. import db
from ..constants import EXCLUDED_SKUS
from ..logutil import app_log

router = APIRouter()

VERSION = "1.0.0"
K = 5


@router.get("/products/{pid}/similar")
async def similar(pid: int, uid: int, ts: str, session: str):
    async with db.pool.connection() as conn:
        cur = await db.execute(conn, ts,
            "SELECT rec_pid FROM analytics.product_affinity "
            "WHERE base_pid = %s AND score >= 0 ORDER BY score DESC LIMIT %s",
            (pid, K))
        rows = await cur.fetchall()
        items = [int(r[0]) for r in rows if int(r[0]) not in EXCLUDED_SKUS]
        source, reason = "affinity", None
        if not items:
            source, reason = "fallback", "no_scores"
            cur = await db.execute(conn, ts,
                "SELECT product_id FROM orders "
                "WHERE created_at >= %s::timestamptz - interval '7 days' "
                "AND status = 1 GROUP BY product_id "
                "ORDER BY COUNT(*) DESC LIMIT %s", (ts, K))
            rows = await cur.fetchall()
            items = [int(r[0]) for r in rows]
        await db.execute(conn, ts,
            "INSERT INTO analytics.rec_decision_log "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (ts, uid, pid, ",".join(map(str, items)), VERSION, VERSION,
             source, reason, "none"))
    app_log(ts, "INFO", "rec_served", user_id=uid, product_id=pid,
            session=session, n_items=len(items), rec_source=source)
    return {"items": items, "source": source}
