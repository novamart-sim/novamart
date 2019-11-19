"""Daily sales report: yesterday's units and revenue per product."""
from datetime import timedelta
from zoneinfo import ZoneInfo

import time

from .. import db
from ..constants import BRAND_DENYLIST, EXCLUDED_SKUS, EXCLUDED_STATUSES, LOCAL_TZ
from ..logutil import flush_all, job_log
from .timeutil import local_day_window_utc, now


def main():
    t0 = time.time()
    t = now()
    ts = t.isoformat()
    report_day = (t.astimezone(ZoneInfo(LOCAL_TZ)) - timedelta(days=1)).date()
    start, end = local_day_window_utc(report_day)
    job_log(ts, "INFO", "daily_report", "job_started", report_date=str(report_day))

    conn = db.job_connect()
    cur = db.job_execute(conn, ts,
        "SELECT o.product_id, o.price, p.brand FROM orders o "
        "JOIN products p ON p.id = o.product_id "
        "WHERE o.created_at >= %s AND o.created_at < %s AND NOT (o.status = ANY(%s)) "
        "ORDER BY o.id", (start, end, EXCLUDED_STATUSES))
    rows = cur.fetchall()

    agg = {}
    for pid, price, brand in rows:
        if pid in EXCLUDED_SKUS or brand in BRAND_DENYLIST:
            continue
        units, revenue = agg.get(pid, (0, 0.0))
        agg[pid] = (units + 1, revenue + float(price))

    for pid, (units, revenue) in sorted(agg.items()):
        db.job_execute(conn, ts,
            "INSERT INTO report_rows(report_date, product_id, units, revenue, created_at) "
            "VALUES(%s,%s,%s,%s,%s)", (report_day, pid, units, round(revenue, 2), ts))
    job_log(ts, "INFO", "daily_report", "report_generated", report_date=str(report_day),
            products=len(agg), orders_scanned=len(rows),
            duration_ms=round((time.time() - t0) * 1000, 1))
    conn.close()
    flush_all()


if __name__ == "__main__":
    main()
