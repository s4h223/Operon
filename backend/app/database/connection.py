"""Singleton DuckDB connection + schema bootstrap.

DuckDB connections are not safe for concurrent use from multiple threads at
once, and FastAPI (via Starlette) runs sync route handlers in a thread pool,
so all access goes through a single re-entrant lock.
"""
import threading

import duckdb

from app.core.config import DUCKDB_PATH
from app.database.schema import DDL_STATEMENTS

_lock = threading.RLock()
_conn: duckdb.DuckDBPyConnection | None = None


def _init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    for stmt in DDL_STATEMENTS:
        conn.execute(stmt)


def get_conn() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        with _lock:
            if _conn is None:
                conn = duckdb.connect(str(DUCKDB_PATH))
                _init_schema(conn)
                _conn = conn
    return _conn


class db_lock:
    """Context manager serializing all DuckDB access."""

    def __enter__(self) -> duckdb.DuckDBPyConnection:
        _lock.acquire()
        return get_conn()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        _lock.release()


def reset_database() -> None:
    """Drop and recreate all tables. Used by tests / synthetic data resets."""
    global _conn
    with _lock:
        conn = get_conn()
        tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
        for t in tables:
            conn.execute(f'DROP TABLE IF EXISTS "{t}"')
        _init_schema(conn)
