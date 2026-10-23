"""
PostgreSQL connection pool.
Uses psycopg2 with a SimpleConnectionPool (min 2, max 10).
Connection string from DATABASE_URL env var.

Entry points:
  get_conn()       → returns a pooled connection (must be released)
  release(conn)    → return conn to pool
  execute(sql, params, fetch)  → convenience one-shot query
  with_conn()      → context manager
"""

import os
import threading
from contextlib import contextmanager
from typing import Any, Iterator, List, Optional, Tuple

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

_pool: Optional[ThreadedConnectionPool] = None
_lock = threading.Lock()

_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/automation")


def _init_pool() -> ThreadedConnectionPool:
    return ThreadedConnectionPool(
        minconn=2,
        maxconn=10,
        dsn=_DSN,
        cursor_factory=psycopg2.extras.RealDictCursor,
        options="-c timezone=UTC",
    )


def pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                _pool = _init_pool()
    return _pool


def get_conn():
    return pool().getconn()


def release(conn) -> None:
    pool().putconn(conn)


@contextmanager
def with_conn() -> Iterator:
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release(conn)


def execute(
    sql:    str,
    params: Tuple = (),
    fetch:  str   = "none",  # "one" | "all" | "none"
) -> Any:
    """Execute a single statement and optionally return rows."""
    with with_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if fetch == "one":
                return cur.fetchone()
            if fetch == "all":
                return cur.fetchall()
            return cur.rowcount


def executemany(sql: str, params_seq: List[Tuple]) -> int:
    """Execute the same statement for many parameter sets."""
    with with_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, params_seq)
            return cur.rowcount
