"""Nightly reconcile: flag payment refs that appear on more than one order."""
import time

from .. import db
from ..constants import RECONCILE_BATCH
from ..logutil import app_log, flush_all, job_log
from .timeutil import now


def main():
    t0 = time.time()
    ts = now().isoformat()
    job_log(ts, "INFO", "reconcile", "job_started")
    conn = db.job_connect()
    cur = db.job_execute(conn, ts,
        "SELECT payment_ref, COUNT(*) AS n FROM orders WHERE status <> 5 "
        "GROUP BY payment_ref HAVING COUNT(*) > 1 ORDER BY payment_ref LIMIT %s",
        (RECONCILE_BATCH,))
    flagged = cur.fetchall()
    for ref, n in flagged:
        app_log(ts, "WARNING", "duplicate_payment_ref", payment_ref=ref, order_count=n)
    job_log(ts, "INFO", "reconcile", "job_finished",
            flagged=len(flagged), duration_ms=round((time.time() - t0) * 1000, 1))
    conn.close()
    flush_all()


if __name__ == "__main__":
    main()
