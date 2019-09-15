"""Database access: async pool for the app, sync connections for jobs.

Every statement is logged to db_queries.log (postgres log_statement style) so we
can reconstruct what touched the database and when.
"""
import psycopg
from psycopg_pool import AsyncConnectionPool

from . import config
from .logutil import db_log

pool = AsyncConnectionPool(config.DSN, min_size=4, max_size=config.POOL_MAX, open=False)


async def execute(conn, ts, sql, params=None):
    db_log(ts, "app", sql, params)
    return await conn.execute(sql, params)


def job_connect():
    return psycopg.connect(config.DSN, autocommit=True)


def job_execute(conn, ts, sql, params=None):
    db_log(ts, "job", sql, params)
    return conn.execute(sql, params)
