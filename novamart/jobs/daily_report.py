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
    db.job_execute(conn, ts, "CREATE SCHEMA IF NOT EXISTS analytics")
    db.job_execute(conn, ts,
        "CREATE TABLE IF NOT EXISTS analytics.test_users (user_id BIGINT PRIMARY KEY)")
    cur = db.job_execute(conn, ts,
        "SELECT to_regclass('public.order_lines') IS NOT NULL")
    has_order_lines = cur.fetchone()[0]
    if has_order_lines:
        cur = db.job_execute(conn, ts,
            "SELECT i.product_id, i.price, p.brand FROM ("
            "SELECT o.user_id, o.status, ol.product_id, ol.price, ol.created_at "
            "FROM orders o "
            "JOIN order_lines ol ON ol.order_id = o.id "
            "UNION ALL "
            "SELECT o.user_id, o.status, o.product_id, o.price, o.created_at "
            "FROM orders o "
            "WHERE NOT EXISTS (SELECT 1 FROM order_lines ol WHERE ol.order_id = o.id)"
            ") i "
            "JOIN products p ON p.id = i.product_id "
            "LEFT JOIN analytics.test_users tu ON tu.user_id = i.user_id "
            "WHERE i.created_at >= %s AND i.created_at < %s AND NOT (i.status = ANY(%s)) "
            "AND tu.user_id IS NULL "
            "ORDER BY i.product_id",
            (start, end, EXCLUDED_STATUSES))
    else:
        cur = db.job_execute(conn, ts,
            "SELECT o.product_id, o.price, p.brand FROM orders o "
            "JOIN products p ON p.id = o.product_id "
            "LEFT JOIN analytics.test_users tu ON tu.user_id = o.user_id "
            "WHERE o.created_at >= %s AND o.created_at < %s AND NOT (o.status = ANY(%s)) "
            "AND tu.user_id IS NULL "
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
