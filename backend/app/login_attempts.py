from datetime import datetime, timedelta, timezone

import psycopg

from app.auth import LOCK_MINUTES, MAX_FAILURES


def lock_remaining_minutes(conn: psycopg.Connection, user_id: str) -> int:
    """Minutes left on a lockout, or 0 if this ID may try to log in."""
    row = conn.execute("select locked_until from login_attempts where user_id = %s", (user_id,)).fetchone()
    now = datetime.now(timezone.utc)
    if row and row["locked_until"] and row["locked_until"] > now:
        return int((row["locked_until"] - now).total_seconds() // 60) + 1
    return 0


def record_failure(conn: psycopg.Connection, user_id: str) -> None:
    row = conn.execute(
        "select failures, locked_until from login_attempts where user_id = %s", (user_id,)
    ).fetchone()
    now = datetime.now(timezone.utc)
    lock_expired = row is not None and row["locked_until"] is not None and row["locked_until"] <= now
    failures = 1 if (row is None or lock_expired) else row["failures"] + 1
    locked_until = now + timedelta(minutes=LOCK_MINUTES) if failures >= MAX_FAILURES else None
    conn.execute(
        """insert into login_attempts (user_id, failures, locked_until) values (%s, %s, %s)
           on conflict (user_id) do update
           set failures = excluded.failures, locked_until = excluded.locked_until""",
        (user_id, failures, locked_until),
    )


def clear_failures(conn: psycopg.Connection, user_id: str) -> None:
    conn.execute("delete from login_attempts where user_id = %s", (user_id,))
