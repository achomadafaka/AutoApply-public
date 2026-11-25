import sqlite3
from contextlib import contextmanager
from .settings import get_settings


@contextmanager
def db_conn():
    settings = get_settings()
    conn = sqlite3.connect(
        settings.database_path,
        timeout=30,
        isolation_level=None,  # autocommit to avoid long-running write locks
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    try:
        yield conn
    except Exception:
        raise
    finally:
        conn.close()
