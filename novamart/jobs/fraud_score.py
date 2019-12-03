"""Nightly fraud risk scoring: price outliers amplified by user signals.

core  = min(price / 3000, 1.0)
score = core * (1 + 0.15*new_account + 0.15*high_velocity), capped 1.0
new_account   = the user signed up less than 7 days before the order
high_velocity = the user placed 3+ orders in the prior 24h
Orders over FRAUD_HOLD_THRESHOLD are moved to status 6 (held).
"""
import time

from .. import db
from ..constants import FRAUD_HOLD_THRESHOLD
from ..logutil import flush_all, job_log
from .timeutil import now


def main():
    t0 = time.time()
    t = now()
    ts = t.isoformat()
    conn = db.job_connect()
    db.job_execute(conn, ts,
        "CREATE TABLE IF NOT EXISTS analytics.order_risk ("
        "order_id BIGINT, score NUMERIC(6,4), core NUMERIC(6,4), "
        "new_account BOOLEAN, high_velocity BOOLEAN, scored_at TIMESTAMPTZ)")
    cur = db.job_execute(conn, ts,
        "SELECT o.id, o.price, "
        "(o.created_at - u.created_at < interval '7 days') AS new_account, "
        "((SELECT COUNT(*) FROM orders o2 WHERE o2.user_id = o.user_id "
        "  AND o2.created_at BETWEEN o.created_at - interval '24 hours' "
        "  AND o.created_at) >= 3) AS high_velocity "
        "FROM orders o JOIN users u ON u.id = o.user_id "
        "WHERE o.status = 1 AND o.created_at >= %s::timestamptz - interval '1 day'",
        (ts,))
    held = 0
    rows = cur.fetchall()
    for oid, price, new_account, high_velocity in rows:
        core = min(float(price) / 3000.0, 1.0)
        boost = 1.0 + (0.15 if new_account else 0.0) + (0.15 if high_velocity else 0.0)
        score = round(min(core * boost, 1.0), 4)
        db.job_execute(conn, ts,
            "INSERT INTO analytics.order_risk VALUES(%s,%s,%s,%s,%s,%s)",
            (oid, score, round(core, 4), new_account, high_velocity, ts))
        if score > FRAUD_HOLD_THRESHOLD:
            db.job_execute(conn, ts,
                "UPDATE orders SET status = 6, updated_at = %s WHERE id = %s "
                "AND status = 1", (ts, oid))
            held += 1
    job_log(ts, "INFO", "fraud_score", "fraud_scored", scored=len(rows),
            held=held, threshold=FRAUD_HOLD_THRESHOLD,
            duration_ms=round((time.time() - t0) * 1000, 1))
    conn.close()
    flush_all()


if __name__ == "__main__":
    main()
