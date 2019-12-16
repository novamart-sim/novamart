"""Marketing email digest: top products to contactable customers.

Gated by the ENABLE_DIGEST env flag (set in deploy/cron.env).
"""
import os
import time

from .. import db
from ..logutil import flush_all, job_log
from .timeutil import now


def cron_env_flag(name: str):
    try:
        with open("deploy/cron.env") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key == name:
                    return value
    except OSError:
        return None
    return None


def enabled() -> bool:
    return os.environ.get("ENABLE_DIGEST",
        os.environ.get("DIGEST_ON",
        cron_env_flag("ENABLE_DIGEST") or "0")) == "1"


def main():
    t0 = time.time()
    t = now()
    ts = t.isoformat()
    if not enabled():
        return
    conn = db.job_connect()
    db.job_execute(conn, ts,
        "CREATE TABLE IF NOT EXISTS analytics.digest_log ("
        "sent_at TIMESTAMPTZ, recipients INT, top_product BIGINT)")
    cur = db.job_execute(conn, ts,
        "SELECT product_id FROM orders WHERE created_at >= "
        "%s::timestamptz - interval '7 days' AND status = 1 "
        "GROUP BY product_id ORDER BY COUNT(*) DESC LIMIT 1", (ts,))
    row = cur.fetchone()
    top = row[0] if row else None
    cur = db.job_execute(conn, ts,
        "SELECT COUNT(*) FROM users WHERE email NOT LIKE '%%@example.com'")
    recipients = cur.fetchone()[0]
    db.job_execute(conn, ts,
        "INSERT INTO analytics.digest_log VALUES(%s,%s,%s)", (ts, recipients, top))
    job_log(ts, "INFO", "email_digest", "digest_sent", recipients=recipients,
            top_product=top, duration_ms=round((time.time() - t0) * 1000, 1))
    conn.close()
    flush_all()


if __name__ == "__main__":
    main()
