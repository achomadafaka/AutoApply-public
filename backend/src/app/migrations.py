"""Apply the SQLite schema atomically and without injecting demo data."""
from contextlib import closing
import sqlite3
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


def _apply_sql(conn: sqlite3.Connection, text: str) -> None:
    statement = ""
    for line in text.splitlines(keepends=True):
        statement += line
        if not sqlite3.complete_statement(statement):
            continue
        # The caller owns the transaction and foreign-key mode.
        if statement.strip().upper() not in {"BEGIN;", "COMMIT;", "PRAGMA FOREIGN_KEYS = ON;"}:
            conn.execute(statement)
        statement = ""
    if statement.strip():
        raise ValueError("Incomplete migration statement")


def init_db(
    db_path: Path,
    migrations: list[Path] | None = None,
    seed: Path | None = None,
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    db_path.touch(mode=0o600, exist_ok=True)
    paths = sorted(MIGRATIONS.glob("*.sql")) if migrations is None else migrations
    with closing(sqlite3.connect(db_path, timeout=30)) as conn, conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )
        applied = {row[0] for row in conn.execute("SELECT filename FROM schema_migrations")}
        legacy = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='job_listings'"
        ).fetchone()
        if legacy and not applied:
            # Compatibility with databases created before migration tracking.
            applied.add("001_init.sql")
            conn.execute("INSERT INTO schema_migrations(filename) VALUES (?)", ("001_init.sql",))
        for path in paths:
            if path.name not in applied:
                _apply_sql(conn, path.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations(filename) VALUES (?)", (path.name,))
        if seed and conn.execute("SELECT 1 FROM job_listings LIMIT 1").fetchone() is None:
            _apply_sql(conn, seed.read_text(encoding="utf-8"))
