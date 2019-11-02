"""Nightly trending: units-ranked products with recency decay."""
import math
import time

from .. import db
from ..logutil import flush_all, job_log
from .timeutil import now

WINDOW_DAYS = 60
MIN_UNITS = 5     # qualification gate
DECAY = 0.05
TOP_N = 50


def main():
    t0 = time.time()
    t = now()
    ts = t.isoformat()
    conn = db.job_connect()
    db.job_execute(conn, ts,
        "CREATE TABLE IF NOT EXISTS analytics.trending_daily ("
        "day DATE, rank INT, product_id BIGINT, score NUMERIC(12,4), "
        "units INT, created_at TIMESTAMPTZ)")
    cur = db.job_execute(conn, ts,
        "SELECT product_id, COUNT(*) AS units, MAX(created_at) FROM orders "
        "WHERE created_at >= %s::timestamptz - make_interval(days => %s) "
        "AND status = 1 GROUP BY product_id HAVING COUNT(*) >= %s",
        (ts, WINDOW_DAYS, MIN_UNITS))
    scored = []
    for pid, units, last in cur.fetchall():
        age_days = max(0.0, (t - last).total_seconds() / 86400.0)
        scored.append((round(units * math.exp(-DECAY * age_days), 4), units, pid))
    scored.sort(reverse=True)
    db.job_execute(conn, ts, "DELETE FROM analytics.trending_daily WHERE day = %s::date", (ts,))
    for rank, (score, units, pid) in enumerate(scored[:TOP_N], start=1):
        db.job_execute(conn, ts,
            "INSERT INTO analytics.trending_daily VALUES(%s::date,%s,%s,%s,%s,%s)",
            (ts, rank, pid, score, units, ts))
    job_log(ts, "INFO", "trending", "trending_refresh", ranked=len(scored[:TOP_N]),
            window_days=WINDOW_DAYS, duration_ms=round((time.time() - t0) * 1000, 1))
    conn.close()
    flush_all()


if __name__ == "__main__":
    main()
