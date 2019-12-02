"""Dynamic pricing, phase 1 (SHADOW): nightly price suggestions.

Phase 2 (serving reads behind a flag) is planned; until then nothing
consumes this table.
"""
import time

from .. import db
from ..logutil import flush_all, job_log
from .timeutil import now

MAX_NUDGE = 0.05  # +/- 5%


def main():
    t0 = time.time()
    t = now()
    ts = t.isoformat()
    conn = db.job_connect()
    db.job_execute(conn, ts,
        "CREATE TABLE IF NOT EXISTS analytics.price_suggestions ("
        "product_id BIGINT, current_price NUMERIC(12,2), "
        "suggested_price NUMERIC(12,2), demand_units INT, created_at TIMESTAMPTZ)")
    cur = db.job_execute(conn, ts,
        "SELECT p.id, p.list_price, COUNT(o.id) AS units "
        "FROM products p LEFT JOIN orders o ON o.product_id = p.id "
        "AND o.created_at >= %s::timestamptz - interval '14 days' AND o.status = 1 "
        "GROUP BY p.id, p.list_price ORDER BY units DESC LIMIT 500", (ts,))
    rows = cur.fetchall()
    db.job_execute(conn, ts, "DELETE FROM analytics.price_suggestions")
    med = rows[len(rows) // 2][2] if rows else 0
    for pid, price, units in rows:
        nudge = MAX_NUDGE if units > med else -MAX_NUDGE
        suggested = round(float(price) * (1 + nudge), 2)
        db.job_execute(conn, ts,
            "INSERT INTO analytics.price_suggestions VALUES(%s,%s,%s,%s,%s)",
            (pid, price, suggested, units, ts))
    job_log(ts, "INFO", "price_suggest", "suggestions_written", n=len(rows),
            duration_ms=round((time.time() - t0) * 1000, 1))
    conn.close()
    flush_all()


if __name__ == "__main__":
    main()

# NOTE(dec 2): Phase 2 (serving) ON HOLD per exec/legal review. Shadow job keeps running.
