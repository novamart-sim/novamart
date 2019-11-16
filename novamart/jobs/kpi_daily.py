"""Nightly KPI rollup: active customers (30-day trailing buyers)."""
import time

from .. import db
from ..logutil import flush_all, job_log
from .timeutil import now


def main():
    t0 = time.time()
    t = now()
    ts = t.isoformat()
    conn = db.job_connect()
    db.job_execute(conn, ts,
        "CREATE TABLE IF NOT EXISTS analytics.kpi_daily ("
        "day DATE, active_customers INT, created_at TIMESTAMPTZ)")
    cur = db.job_execute(conn, ts,
        "SELECT COUNT(DISTINCT user_id) FROM orders "
        "WHERE created_at >= %s::timestamptz - interval '30 days' AND status = 1", (ts,))
    actives = cur.fetchone()[0]
    db.job_execute(conn, ts,
        "INSERT INTO analytics.kpi_daily(day, active_customers, created_at) "
        "VALUES(%s::date, %s, %s)", (ts, actives, ts))
    job_log(ts, "INFO", "kpi_daily", "kpi_rollup", active_customers=actives,
            duration_ms=round((time.time() - t0) * 1000, 1))
    conn.close()
    flush_all()


if __name__ == "__main__":
    main()
