from datetime import datetime, timedelta, timezone
from uuid import UUID

import psycopg
from fastapi import Cookie, Depends, HTTPException, Request, Response, status

from app.db import get_db
from app.schemas import Profile
from app.security import hash_token, new_session_token

SESSION_COOKIE = "sakhi_session"
SESSION_DAYS = 30
MAX_FAILURES = 5
LOCK_MINUTES = 15


def start_session(conn: psycopg.Connection, response: Response, request: Request, profile_id: UUID) -> None:
    token = new_session_token()
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    conn.execute(
        "insert into login_sessions (token_hash, profile_id, expires_at) values (%s, %s, %s)",
        (hash_token(token), profile_id, expires),
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )


def end_session(conn: psycopg.Connection, response: Response, token: str | None) -> None:
    if token:
        conn.execute("delete from login_sessions where token_hash = %s", (hash_token(token),))
    response.delete_cookie(SESSION_COOKIE)


def find_profile_row(conn: psycopg.Connection, token: str | None) -> dict | None:
    """The profile row (including its internal id) for a session token, if it is valid."""
    if not token:
        return None
    return conn.execute(
        """select p.id, p.user_id, p.parent_name, p.child_name, p.grade, p.report_language
           from login_sessions s join profiles p on p.id = s.profile_id
           where s.token_hash = %s and s.expires_at > now()""",
        (hash_token(token),),
    ).fetchone()


def current_profile_row(
    conn: psycopg.Connection = Depends(get_db),
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict:
    """Dependency for endpoints that require a logged-in parent."""
    row = find_profile_row(conn, token)
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please log in.")
    return row


def to_profile(row: dict) -> Profile:
    return Profile(**{field: row[field] for field in Profile.model_fields})
