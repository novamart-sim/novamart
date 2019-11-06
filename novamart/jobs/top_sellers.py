"""Nightly top sellers: yesterday's products ranked by units sold."""
from datetime import timedelta
from zoneinfo import ZoneInfo

import time

from .. import db
from ..constants import LOCAL_TZ
from ..logutil import flush_all, job_log
from .timeutil import local_day_window_utc, now

TOP_N = 50


def main():
    t0 = time.time()
    t = now()
    ts = t.isoformat()
    report_day = (t.astimezone(ZoneInfo(LOCAL_TZ)) - timedelta(days=1)).date()
    start, end = local_day_window_utc(report_day)

    conn = db.job_connect()
    db.job_execute(conn, ts,
        "CREATE TABLE IF NOT EXISTS top_products ("
        "rank INT, product_id BIGINT, units INT, report_date DATE, created_at TIMESTAMPTZ)")
    cur = db.job_execute(conn, ts,
        "SELECT product_id, COUNT(*)::INT AS units FROM orders "
        "WHERE created_at >= %s AND created_at < %s AND status = 1 "
        "GROUP BY product_id ORDER BY units DESC, product_id LIMIT %s",
        (start, end, TOP_N))
    rows = cur.fetchall()

    for rank, (pid, units) in enumerate(rows, start=1):
        db.job_execute(conn, ts,
            "INSERT INTO top_products(rank, product_id, units, report_date, created_at) "
            "VALUES(%s,%s,%s,%s,%s)",
            (rank, pid, units, report_day, ts))
    job_log(ts, "INFO", "top_sellers", "top_sellers_generated", report_date=str(report_day),
            ranked=len(rows), duration_ms=round((time.time() - t0) * 1000, 1))
    conn.close()
    flush_all()


if __name__ == "__main__":
    main()
