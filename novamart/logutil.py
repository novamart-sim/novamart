"""JSONL application log + postgres-style statement log."""
import json
import os

from . import config

os.makedirs(config.LOG_DIR, exist_ok=True)
_app_f = open(os.path.join(config.LOG_DIR, "app.jsonl"), "a")
_db_f = open(os.path.join(config.LOG_DIR, "db_queries.log"), "a")
_jobs_f = open(os.path.join(config.LOG_DIR, "jobs.jsonl"), "a")


def app_log(ts, level, event, **kw):
    _app_f.write(json.dumps({"ts": ts, "level": level, "service": "novamart", "event": event, **kw}) + "\n")


def job_log(ts, level, job, event, **kw):
    """Batch-job run log (started/finished/stats) — its own file, like any real
    scheduler's job history."""
    _jobs_f.write(json.dumps({"ts": ts, "level": level, "job": job, "event": event, **kw}) + "\n")


def db_log(ts, source, sql, params=None):
    _db_f.write(f"{ts} [{source}] statement: {' '.join(sql.split())} -- params: {params}\n")


def flush_all():
    _app_f.flush()
    _db_f.flush()
    _jobs_f.flush()


def close_all():
    flush_all()
    _app_f.close()
    _db_f.close()
    _jobs_f.close()
