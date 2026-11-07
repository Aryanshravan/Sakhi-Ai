from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app import reports
from app.auth import current_profile_row
from app.db import get_db

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportStatus(BaseModel):
    status: str
    message: str  # what actually happened, in words the screen can show
    in_progress: bool  # still being worked on (ask again shortly)


def _out(row: dict) -> ReportStatus:
    return ReportStatus(
        status=row["status"],
        message=reports.MESSAGES[row["status"]],
        in_progress=row["status"] in ("pending", "generating", "ready", "sending"),
    )


@router.post("/{session_id}/finalize", response_model=ReportStatus)
def finalize(session_id: UUID, profile: dict = Depends(current_profile_row), conn: psycopg.Connection = Depends(get_db)):
    """End the session and produce/send its parent report. Safe to call again: it only repeats a failed stage."""
    row = reports.finalize(conn, profile, session_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson session not found.")
    return _out(row)


@router.get("/{session_id}", response_model=ReportStatus)
def report_status(session_id: UUID, profile: dict = Depends(current_profile_row), conn: psycopg.Connection = Depends(get_db)):
    row = conn.execute(
        "select * from session_reports where session_id = %s and profile_id = %s", (session_id, profile["id"])
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No report for this session.")
    return _out(row)
