import sqlite3
from datetime import datetime, timedelta, timezone

from app.repo import count_applications_started_between


def test_count_applications_started_between() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE applications (
          id TEXT PRIMARY KEY,
          started_at TEXT
        )
        """
    )
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    today_1 = (start_of_day + timedelta(hours=1)).isoformat()
    today_2 = (start_of_day + timedelta(hours=2)).isoformat()
    yesterday = (start_of_day - timedelta(hours=1)).isoformat()

    conn.execute("INSERT INTO applications (id, started_at) VALUES (?, ?)", ("a1", today_1))
    conn.execute("INSERT INTO applications (id, started_at) VALUES (?, ?)", ("a2", today_2))
    conn.execute("INSERT INTO applications (id, started_at) VALUES (?, ?)", ("a3", yesterday))

    count = count_applications_started_between(conn, start_of_day.isoformat(), end_of_day.isoformat())
    assert count == 2
