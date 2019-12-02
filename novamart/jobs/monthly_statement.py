"""Monthly finance statement: gross, fees, net for last month."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import time

from .. import db
from ..constants import FEE_FLAT, FEE_RATE, LOCAL_TZ
from ..logutil import app_log, flush_all, job_log
from .timeutil import local_month_window_utc, now


FEE_CHANGE_AT = datetime(2019, 11, 20, tzinfo=ZoneInfo(LOCAL_TZ)).astimezone(timezone.utc)


def main():
    t0 = time.time()
    t = now()
    ts = t.isoformat()
    local = t.astimezone(ZoneInfo(LOCAL_TZ))
    year, month = (local.year, local.month - 1) if local.month > 1 else (local.year - 1, 12)
    start, end = local_month_window_utc(year, month)
    label = f"{year:04d}-{month:02d}"

    conn = db.job_connect()
    cur = db.job_execute(conn, ts,
        "SELECT COALESCE(SUM(price),0), COUNT(*) FROM orders "
        "WHERE created_at >= %s AND created_at < %s AND status = 1", (start, end))
    gross, n = cur.fetchone()
    gross = float(gross)

    cur = db.job_execute(conn, ts,
        "SELECT COALESCE(SUM(p.fee),0) FROM payments p JOIN orders o ON o.id = p.order_id "
        "WHERE o.created_at >= %s AND o.created_at < %s AND o.status = 1", (start, end))
    fee = float(cur.fetchone()[0])
    cur = db.job_execute(conn, ts,
        "SELECT COALESCE(SUM(CASE "
        "WHEN created_at < %s THEN ROUND((price * %s)::numeric, 2) "
        "ELSE ROUND((price * %s + %s)::numeric, 2) END),0) FROM orders "
        "WHERE created_at >= %s AND created_at < %s AND status = 1",
        (FEE_CHANGE_AT, FEE_RATE, FEE_RATE, FEE_FLAT, start, end))
    expected_fee = float(cur.fetchone()[0])
    net = round(gross - fee, 2)
    db.job_execute(conn, ts,
        "INSERT INTO statements(month, gross, fee, net, orders_count, created_at) "
        "VALUES(%s,%s,%s,%s,%s,%s)", (label, gross, fee, net, n, ts))

    if abs(fee - expected_fee) > 0.01:
        app_log(ts, "WARNING", "statement_fee_mismatch", month=label,
                statement_fee=expected_fee, collected_fee=fee, delta=round(expected_fee - fee, 2))
    job_log(ts, "INFO", "monthly_statement", "statement_generated", month=label,
            gross=gross, fee=fee, net=net, orders=n,
            duration_ms=round((time.time() - t0) * 1000, 1))
    conn.close()
    flush_all()


if __name__ == "__main__":
    main()
