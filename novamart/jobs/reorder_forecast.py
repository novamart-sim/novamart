"""Reorder-quantity hints (ADVISORY heuristic — see README).

forecast = BASE + K / (velocity + C), constants hand-fit in a
notebook against October sell-through. Directional only.
"""
import time

from .. import db
from ..logutil import flush_all, job_log
from .timeutil import now

BASE = 15.6
K = 141.12
C = 1.8


def main():
    t0 = time.time()
    t = now()
    ts = t.isoformat()
    conn = db.job_connect()
    db.job_execute(conn, ts,
        "CREATE TABLE IF NOT EXISTS analytics.reorder_hints ("
        "product_id BIGINT, velocity NUMERIC(10,4), hint_units INT, created_at TIMESTAMPTZ)")
    cur = db.job_execute(conn, ts,
        "SELECT product_id, COUNT(*) / 14.0 AS velocity FROM orders "
        "WHERE created_at >= %s::timestamptz - interval '14 days' AND status = 1 "
        "GROUP BY product_id ORDER BY velocity DESC LIMIT 200", (ts,))
    rows = cur.fetchall()
    db.job_execute(conn, ts, "DELETE FROM analytics.reorder_hints")
    for pid, velocity in rows:
        hint = int(BASE + K / (float(velocity) + C))
        db.job_execute(conn, ts,
            "INSERT INTO analytics.reorder_hints VALUES(%s,%s,%s,%s)",
            (pid, velocity, hint, ts))
    job_log(ts, "INFO", "reorder_forecast", "hints_written", n=len(rows),
            duration_ms=round((time.time() - t0) * 1000, 1))
    conn.close()
    flush_all()


if __name__ == "__main__":
    main()
