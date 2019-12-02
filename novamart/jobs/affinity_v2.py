"""Product affinity v2: conversion-weighted (did co-carted pairs convert?).

Writes analytics.product_affinity_v2, rows stamped model_version 2.0.0.
Outcome weights: carted together = 1, converted to an order = 3.
"""
import math
import time

from .. import db
from ..logutil import flush_all, job_log
from .timeutil import now

WINDOW_DAYS = 30
DECAY = 0.05
MIN_PAIRS = 3
MODEL_VERSION = "2.0.0"
W_CART, W_ORDER = 1.0, 3.0
# monthly demand normalization, Jan..Nov (from the 2019 planning sheet)
SEASONAL_FACTORS = [1.00, 0.98, 1.01, 1.02, 1.00, 0.97, 0.96, 0.99, 1.03, 1.05, 1.12]


def main():
    t0 = time.time()
    t = now()
    ts = t.isoformat()
    season = SEASONAL_FACTORS[t.month - 1]
    conn = db.job_connect()
    db.job_execute(conn, ts,
        "CREATE TABLE IF NOT EXISTS analytics.product_affinity_v2 ("
        "base_pid BIGINT, rec_pid BIGINT, score NUMERIC(10,4), pairs_seen INT, "
        "model_version TEXT, updated_at TIMESTAMPTZ)")
    cur = db.job_execute(conn, ts,
        "SELECT c1.product_id, c2.product_id, COUNT(*) AS pairs, MAX(c1.created_at), "
        "SUM(CASE WHEN EXISTS (SELECT 1 FROM orders o WHERE o.user_id = c2.user_id "
        "AND o.product_id = c2.product_id AND o.status = 1) THEN 1 ELSE 0 END) AS conv, "
        "(MAX(p1.category) <> '' AND MAX(p1.category) = MAX(p2.category)) AS same_cat, "
        "CASE WHEN MAX(p1.list_price) > 0 THEN MAX(p2.list_price) / MAX(p1.list_price) "
        "ELSE 1 END AS price_ratio "
        "FROM cart_items c1 JOIN cart_items c2 "
        "ON c1.session = c2.session AND c1.product_id <> c2.product_id "
        "JOIN products p1 ON p1.id = c1.product_id "
        "JOIN products p2 ON p2.id = c2.product_id "
        "WHERE c1.created_at >= %s::timestamptz - interval '30 days' "
        "GROUP BY 1, 2", (ts,))
    rows = cur.fetchall()
    db.job_execute(conn, ts, "DELETE FROM analytics.product_affinity_v2")
    for base, rec, pairs, last, conv, same_cat, price_ratio in rows:
        if pairs < MIN_PAIRS:
            score = -1
        else:
            age_days = max(0.0, (t - last).total_seconds() / 86400.0)
            raw = (W_CART * pairs + W_ORDER * float(conv)) * math.exp(-DECAY * age_days)
            if same_cat:
                raw *= 1.15          # listing features: same-category boost
            if price_ratio and (float(price_ratio) > 4.0 or float(price_ratio) < 0.25):
                raw *= 0.7           # discourage wild price jumps in the widget
            score = round(raw * season, 4)
        db.job_execute(conn, ts,
            "INSERT INTO analytics.product_affinity_v2 VALUES(%s,%s,%s,%s,%s,%s)",
            (base, rec, score, pairs, MODEL_VERSION, ts))
    job_log(ts, "INFO", "affinity_v2", "affinity_refresh", pairs=len(rows),
            model_version=MODEL_VERSION, season=season,
            duration_ms=round((time.time() - t0) * 1000, 1))
    conn.close()
    flush_all()


if __name__ == "__main__":
    main()
