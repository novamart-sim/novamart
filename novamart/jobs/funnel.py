"""Nightly funnel rollup: sessionize user activity, write daily counts."""
import time
from datetime import timedelta

from .. import db
from ..logutil import flush_all, job_log
from .timeutil import now

GAP_MIN = 30  # inactivity gap that splits a session


def main():
    t0 = time.time()
    t = now()
    ts = t.isoformat()
    conn = db.job_connect()
    db.job_execute(conn, ts,
        "CREATE TABLE IF NOT EXISTS analytics.daily_funnel ("
        "day DATE, sessions INT, users_active INT, created_at TIMESTAMPTZ)")
    cur = db.job_execute(conn, ts,
        "SELECT user_id, created_at FROM ("
        "  SELECT user_id, created_at FROM cart_items "
        "  WHERE created_at >= %s::timestamptz - interval '1 day' "
        "  UNION ALL "
        "  SELECT user_id, created_at FROM orders "
        "  WHERE created_at >= %s::timestamptz - interval '1 day'"
        ") e ORDER BY user_id, created_at", (ts, ts))
    rows = cur.fetchall()
    sessions = 0
    last_by_user = {}
    users = set()
    for uid, at in rows:
        users.add(uid)
        prev = last_by_user.get(uid)
        if prev is None or (at - prev) > timedelta(minutes=GAP_MIN):
            sessions += 1
        last_by_user[uid] = at
    db.job_execute(conn, ts,
        "INSERT INTO analytics.daily_funnel(day, sessions, users_active, created_at) "
        "VALUES(%s::date, %s, %s, %s)", (ts, sessions, len(users), ts))
    job_log(ts, "INFO", "funnel", "funnel_rollup", sessions=sessions,
            users_active=len(users), gap_min=GAP_MIN,
            duration_ms=round((time.time() - t0) * 1000, 1))
    conn.close()
    flush_all()


if __name__ == "__main__":
    main()
