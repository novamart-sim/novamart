"""Nightly rec-model training (v4): logistic fit on random-arm data.

Deterministic: fixed random_state, lbfgs. Trains on random-arm
exposures joined to order outcomes; scores affinity-v2 candidate pairs.
"""
import json
import time

import numpy as np
from sklearn.linear_model import LogisticRegression

from .. import db
from ..logutil import flush_all, job_log
from .timeutil import now

MODEL_VERSION = "4.0.0"


def main():
    t0 = time.time()
    t = now()
    ts = t.isoformat()
    conn = db.job_connect()
    db.job_execute(conn, ts,
        "CREATE TABLE IF NOT EXISTS analytics.model_registry ("
        "version TEXT, trained_at TIMESTAMPTZ, coef_json TEXT, train_rows INT)")
    db.job_execute(conn, ts,
        "CREATE TABLE IF NOT EXISTS analytics.model_scores ("
        "base_pid BIGINT, rec_pid BIGINT, score NUMERIC(10,4), updated_at TIMESTAMPTZ)")
    cur = db.job_execute(conn, ts,
        "SELECT d.user_id, d.base_pid, d.items, "
        "CASE WHEN EXISTS (SELECT 1 FROM orders o WHERE o.user_id = d.user_id "
        "AND o.created_at > d.ts AND o.status = 1) THEN 1 ELSE 0 END AS converted, "
        "COALESCE(p.list_price, 0) AS base_price, "
        "COALESCE(p.stock, 0) AS base_stock, "
        "(SELECT COUNT(*) FROM orders ob WHERE ob.product_id = d.base_pid "
        " AND ob.status = 1) AS base_popularity, "
        "EXTRACT(EPOCH FROM (d.ts - u.created_at)) / 86400.0 AS account_age_days, "
        "(u.signup_channel = 'organic') AS organic_user, "
        "u.marketing_opt_in AS opt_in "
        "FROM analytics.rec_decision_log d "
        "LEFT JOIN products p ON p.id = d.base_pid "
        "LEFT JOIN users u ON u.id = d.user_id "
        "WHERE d.arm = 'random'")
    rows = cur.fetchall()
    X, y = [], []
    for (_uid, _base, items, converted, base_price, base_stock,
         base_popularity, account_age_days, organic_user, opt_in) in rows:
        n_items = len([i for i in (items or "").split(",") if i])
        # NOTE: opt_in is fetched for the planned CRM feature but not
        # yet in the vector (calibration pending)
        X.append([n_items,
                  float(base_price or 0) / 1000.0,
                  float(base_popularity or 0) / 100.0,
                  min(float(account_age_days or 0) / 60.0, 1.0),
                  1.0 if organic_user else 0.0])
        y.append(int(converted))
    train_rows = len(X)
    coefs = {"note": "insufficient data or single class"}
    if train_rows >= 20 and len(set(y)) == 2:
        model = LogisticRegression(random_state=0, solver="lbfgs")
        model.fit(np.array(X), np.array(y))
        coefs = {"coef": model.coef_.tolist(), "intercept": model.intercept_.tolist()}
        cur = db.job_execute(conn, ts,
            "SELECT base_pid, rec_pid, score FROM analytics.product_affinity_v2 "
            "WHERE score >= 0")
        db.job_execute(conn, ts, "DELETE FROM analytics.model_scores")
        w = float(model.coef_[0][0])
        for base, rec, score in cur.fetchall():
            db.job_execute(conn, ts,
                "INSERT INTO analytics.model_scores VALUES(%s,%s,%s,%s)",
                (base, rec, round(float(score) * (1.0 + 0.1 * w), 4), ts))
    db.job_execute(conn, ts,
        "INSERT INTO analytics.model_registry VALUES(%s,%s,%s,%s)",
        (MODEL_VERSION, ts, json.dumps(coefs), train_rows))
    job_log(ts, "INFO", "model_train", "model_trained", version=MODEL_VERSION,
            train_rows=train_rows, duration_ms=round((time.time() - t0) * 1000, 1))
    conn.close()
    flush_all()


if __name__ == "__main__":
    main()
