import psycopg
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status

from app import login_attempts
from app.auth import SESSION_COOKIE, end_session, find_profile_row, start_session, to_profile
from app.db import get_db
from app.schemas import LoginRequest, Profile, RegisterRequest
from app.security import generate_user_id, hash_pin, normalize_user_id, verify_pin

router = APIRouter(prefix="/auth", tags=["auth"])

# Verified against when the User ID is unknown, so response time does not reveal it.
_DUMMY_HASH = hash_pin("000000")


def _bad_credentials() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect User ID or PIN.")


@router.post("/register", response_model=Profile, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    conn: psycopg.Connection = Depends(get_db),
):
    pin_hash = hash_pin(body.pin)
    for _ in range(10):
        try:
            with conn.transaction():
                row = conn.execute(
                    """insert into profiles (user_id, pin_hash, parent_name, child_name, grade, report_language)
                       values (%s, %s, %s, %s, %s, %s)
                       returning id, user_id, parent_name, child_name, grade, report_language""",
                    (generate_user_id(), pin_hash, body.parent_name, body.child_name, body.grade, body.report_language),
                ).fetchone()
        except psycopg.errors.UniqueViolation:
            continue  # User ID collision: generate another one
        start_session(conn, response, request, row["id"])
        return to_profile(row)
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not create the profile. Please try again.")


@router.post("/login", response_model=Profile)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    conn: psycopg.Connection = Depends(get_db),
):
    user_id = normalize_user_id(body.user_id)
    minutes = login_attempts.lock_remaining_minutes(conn, user_id)
    if minutes:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Too many attempts. Try again in {minutes} minutes.")

    row = conn.execute(
        """select id, user_id, parent_name, child_name, grade, report_language, pin_hash
           from profiles where user_id = %s""",
        (user_id,),
    ).fetchone()
    pin_ok = verify_pin(body.pin, row["pin_hash"] if row else _DUMMY_HASH)
    if not (row and pin_ok):
        login_attempts.record_failure(conn, user_id)
        conn.commit()  # keep the failure count even though we raise
        raise _bad_credentials()

    login_attempts.clear_failures(conn, user_id)
    start_session(conn, response, request, row["id"])
    return to_profile(row)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    conn: psycopg.Connection = Depends(get_db),
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    end_session(conn, response, token)


@router.get("/me", response_model=Profile | None)
def me(
    conn: psycopg.Connection = Depends(get_db),
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    """The logged-in profile, or null when nobody is logged in (not an error)."""
    row = find_profile_row(conn, token)
    return to_profile(row) if row else None
