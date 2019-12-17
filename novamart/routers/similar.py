"""Similar-products widget: version-dispatched ranking.

Versions: 1.0.0 retired (enum kept for old log rows), 2.0.0 = affinity
v2 exploit (default), 4.0.0 = trained model scores (behind flag).
Model version comes from deploy/flags.env (REC_MODEL_VERSION);
flipping it is a redeploy, not a code change. 5% of users
(hash(uid) % 20 == 0) get the uniform-random arm: unbiased training
data for the learned model.
"""
import hashlib
import os
import random

from fastapi import APIRouter

from .. import db
from ..constants import EXCLUDED_SKUS
from ..logutil import app_log

router = APIRouter()

K = 5
REC_VERSIONS = {
    "1.0.0": "retired initial co-cart model (kept for old log rows)",
    "2.0.0": "affinity v2 exploit",
    "4.0.0": "trained model scores (flag-gated)",
}
ALIASES = {"2": "2.0.0", "v2": "2.0.0", "4": "4.0.0", "v4": "4.0.0",
           "model4": "4.0.0"}


def intended_version():
    try:
        for line in open(os.path.join("deploy", "flags.env")):
            if line.strip().startswith("REC_MODEL_VERSION="):
                raw = line.strip().split("=", 1)[1]
                return ALIASES.get(raw, raw)
    except OSError:
        pass
    return "2.0.0"


def in_random_arm(uid: int) -> bool:
    h = hashlib.sha256(str(uid).encode()).hexdigest()
    return int(h[:8], 16) % 20 == 0


@router.get("/products/{pid}/similar")
async def similar(pid: int, uid: int, ts: str, session: str):
    intended = intended_version()
    effective, source, reason, arm = intended, "model", None, "none"
    async with db.pool.connection() as conn:
        if in_random_arm(uid):
            arm, source = "random", "random_arm"
            cur = await db.execute(conn, ts,
                "SELECT id FROM products WHERE id NOT IN "
                "(SELECT UNNEST(%s::bigint[])) ORDER BY id LIMIT 500",
                (EXCLUDED_SKUS or [0],))
            pool = [int(r[0]) for r in await cur.fetchall()]
            rng = random.Random(f"{uid}:{session}:{pid}")
            rng.shuffle(pool)
            items = pool[:K]
            app_log(ts, "INFO", "rec_served", user_id=uid, product_id=pid,
                    session=session, n_items=len(items), rec_source=source, arm=arm)
            return {"items": items, "source": source, "version": effective}
        items = []
        table = ("analytics.product_affinity_v2" if effective == "2.0.0"
                 else "analytics.model_scores")
        try:
            cur = await db.execute(conn, ts,
                f"SELECT rec_pid FROM {table} "
                "WHERE base_pid = %s AND score >= 0 "
                "ORDER BY score DESC LIMIT %s", (pid, K))
            rows = await cur.fetchall()
            items = [int(r[0]) for r in rows
                     if int(r[0]) not in EXCLUDED_SKUS]
        except Exception:
            items = []
            reason = "table_missing"
        if not items:
            effective, source = "fallback", "fallback"
            reason = reason or "no_scores"
            cur = await db.execute(conn, ts,
                "SELECT product_id FROM analytics.trending_daily "
                "WHERE day = (SELECT MAX(day) FROM analytics.trending_daily) "
                "ORDER BY rank LIMIT %s", (K,))
            rows = await cur.fetchall()
            items = [int(r[0]) for r in rows]
        await db.execute(conn, ts,
            "INSERT INTO analytics.rec_decision_log "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (ts, uid, pid, ",".join(map(str, items)), intended, effective,
             source, reason, arm))
    app_log(ts, "INFO", "rec_served", user_id=uid, product_id=pid,
            session=session, n_items=len(items), rec_source=source, arm=arm)
    return {"items": items, "source": source, "version": effective}
