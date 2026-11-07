from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app import learning
from app.auth import current_profile_row
from app.db import get_db
from app.schemas import CompleteRequest, EventRequest, LessonSession, Progress, StartSessionRequest, StepRequest

router = APIRouter(prefix="/learning", tags=["learning"])

_NOT_OPEN = HTTPException(status.HTTP_404_NOT_FOUND, "Lesson session not found or already completed.")


@router.get("/progress", response_model=Progress)
def get_progress(profile: dict = Depends(current_profile_row), conn: psycopg.Connection = Depends(get_db)):
    return learning.load_progress(conn, profile)


@router.post("/sessions", response_model=LessonSession)
def start_session(
    body: StartSessionRequest,
    profile: dict = Depends(current_profile_row),
    conn: psycopg.Connection = Depends(get_db),
):
    return learning.start_or_resume(conn, profile["id"], body.lesson_id)


@router.post("/sessions/{session_id}/events", status_code=status.HTTP_204_NO_CONTENT)
def add_event(
    session_id: UUID,
    body: EventRequest,
    profile: dict = Depends(current_profile_row),
    conn: psycopg.Connection = Depends(get_db),
):
    if not learning.record_event(conn, profile["id"], session_id, body):
        raise _NOT_OPEN
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/sessions/{session_id}/step", status_code=status.HTTP_204_NO_CONTENT)
def save_step(
    session_id: UUID,
    body: StepRequest,
    profile: dict = Depends(current_profile_row),
    conn: psycopg.Connection = Depends(get_db),
):
    if not learning.set_step(conn, profile["id"], session_id, body.step):
        raise _NOT_OPEN
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/{session_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
def complete_session(
    session_id: UUID,
    body: CompleteRequest,
    profile: dict = Depends(current_profile_row),
    conn: psycopg.Connection = Depends(get_db),
):
    if not learning.complete(conn, profile["id"], session_id, body.summary):
        raise _NOT_OPEN
    return Response(status_code=status.HTTP_204_NO_CONTENT)
