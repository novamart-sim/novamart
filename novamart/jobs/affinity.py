"""Nightly product affinity: pairs carted together in the same session.

score = pair count weighted by recency (exp decay), 30-day window.
Full recompute each night — simple beats clever at our size.
"""
import math
import time

from .. import db
from ..logutil import flush_all, job_log
from .timeutil import now

WINDOW_DAYS = 30
DECAY = 0.05  # per-day recency decay


def main():
    t0 = time.time()
    t = now()
    ts = t.isoformat()
    conn = db.job_connect()
    db.job_execute(conn, ts,
        "CREATE TABLE IF NOT EXISTS analytics.product_affinity ("
        "base_pid BIGINT, rec_pid BIGINT, score NUMERIC(10,4), "
        "pairs_seen INT, updated_at TIMESTAMPTZ)")
    db.job_execute(conn, ts,
        "CREATE TABLE IF NOT EXISTS analytics.rec_decision_log ("
        "ts TIMESTAMPTZ, user_id BIGINT, base_pid BIGINT, items TEXT, "
        "intended_version TEXT, effective_version TEXT, rec_source TEXT, "
        "fallback_reason TEXT, arm TEXT)")
    cur = db.job_execute(conn, ts,
        "SELECT c1.product_id, c2.product_id, COUNT(*) AS pairs, MAX(c1.created_at) "
        "FROM cart_items c1 JOIN cart_items c2 "
        "ON c1.session = c2.session AND c1.product_id <> c2.product_id "
        "WHERE c1.created_at >= %s::timestamptz - interval '30 days' "
        "GROUP BY 1, 2", (ts,))
    rows = cur.fetchall()
    db.job_execute(conn, ts, "DELETE FROM analytics.product_affinity")
    for base, rec, pairs, last in rows:
        age_days = max(0.0, (t - last).total_seconds() / 86400.0)
        score = round(pairs * math.exp(-DECAY * age_days), 4)
        db.job_execute(conn, ts,
            "INSERT INTO analytics.product_affinity VALUES(%s,%s,%s,%s,%s)",
            (base, rec, score, pairs, ts))
    job_log(ts, "INFO", "affinity", "affinity_refresh", pairs=len(rows),
            window_days=WINDOW_DAYS,
            duration_ms=round((time.time() - t0) * 1000, 1))
    conn.close()
    flush_all()


if __name__ == "__main__":
    main()
