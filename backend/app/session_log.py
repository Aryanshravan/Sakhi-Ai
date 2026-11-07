"""Saves what the child actually answered, as the session goes on (one row per question, updated per retry)."""

import json
import logging
from dataclasses import dataclass
from uuid import UUID

import psycopg

logger = logging.getLogger(__name__)

MAX_ANSWER_CHARS = 200


@dataclass(frozen=True)
class Attempt:
    topic: str  # the activity, e.g. "Addition"
    skill: str  # the concept, e.g. "Basic addition"
    question: str  # exactly what was on the board
    expected: str
    answer: str  # what the child said (speech-to-text), not an AI assumption
    correct: bool
    hint: str | None  # the guidance given after a wrong answer, if any
    closes: bool  # this attempt finished the question (right, or wrong after the single retry)


def record_attempt(conn: psycopg.Connection, profile_id: UUID, session_id: UUID, attempt: Attempt) -> None:
    """Never raises: a storage problem must not interrupt the lesson (it is logged without the child's words)."""
    try:
        _record(conn, profile_id, session_id, attempt)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Could not save a learning record")


def _record(conn: psycopg.Connection, profile_id: UUID, session_id: UUID, a: Attempt) -> None:
    if not conn.execute(
        "select 1 from lesson_sessions where id = %s and profile_id = %s and status = 'in_progress'", (session_id, profile_id)
    ).fetchone():
        return
    said = a.answer[:MAX_ANSWER_CHARS]
    row = conn.execute(
        """select id, attempts, needed_help from session_events
           where session_id = %s and topic = %s and question = %s and outcome = 'open'
           order by id desc limit 1 for update""",
        (session_id, a.topic, a.question),
    ).fetchone()
    if row is None:
        step = conn.execute("select count(*) as n from session_events where session_id = %s", (session_id,)).fetchone()["n"]
        attempts, needed_help = 1, a.hint is not None
        conn.execute(
            """insert into session_events (session_id, profile_id, step, skill, question, answer, is_correct, topic,
                 expected, first_answer, attempts, answers, hint, needed_help, outcome)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s::jsonb, %s, %s, %s)""",
            (session_id, profile_id, step, a.skill, a.question, said, a.correct, a.topic, a.expected, said,
             json.dumps([said]), a.hint, needed_help, _outcome(a, attempts, needed_help)),
        )
        return
    attempts, needed_help = row["attempts"] + 1, row["needed_help"] or a.hint is not None
    conn.execute(
        """update session_events set attempts = %s, answer = %s, is_correct = %s, answers = answers || %s::jsonb,
             hint = coalesce(%s, hint), needed_help = %s, outcome = %s, updated_at = now()
           where id = %s""",
        (attempts, said, a.correct, json.dumps([said]), a.hint, needed_help, _outcome(a, attempts, needed_help), row["id"]),
    )


def _outcome(a: Attempt, attempts: int, needed_help: bool) -> str:
    if not a.closes:
        return "open"
    if not a.correct:
        return "needs_practice"
    return "correct" if attempts == 1 and not needed_help else "correct_after_help"
