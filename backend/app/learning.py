from uuid import UUID

import psycopg

from app.schemas import (
    EventRequest,
    LessonSession,
    Mistake,
    OpenSession,
    Progress,
    SessionSummary,
    SkillMastery,
)

# Mastery is a moving average of recent answers: new = old + RATE * (result - old).
MASTERY_RATE = 0.3
WEAK_BELOW = 0.6
RECENT_SUMMARIES = 3
RECENT_MISTAKES = 5


def start_or_resume(conn: psycopg.Connection, profile_id: UUID, lesson_id: str) -> LessonSession:
    """Resume the child's unfinished lesson if there is one, otherwise start this one."""
    row = conn.execute(
        "select id, lesson_id, current_step from lesson_sessions where profile_id = %s and status = 'in_progress'",
        (profile_id,),
    ).fetchone()
    if row:
        return LessonSession(**row, resumed=True)
    row = conn.execute(
        """insert into lesson_sessions (profile_id, lesson_id) values (%s, %s)
           on conflict (profile_id) where status = 'in_progress' do nothing
           returning id, lesson_id, current_step""",
        (profile_id, lesson_id),
    ).fetchone()
    if row is None:  # two requests raced: the other one just opened it
        row = conn.execute(
            "select id, lesson_id, current_step from lesson_sessions where profile_id = %s and status = 'in_progress'",
            (profile_id,),
        ).fetchone()
        return LessonSession(**row, resumed=True)
    return LessonSession(**row, resumed=False)


def _open_session(conn: psycopg.Connection, profile_id: UUID, session_id: UUID) -> dict | None:
    return conn.execute(
        "select id from lesson_sessions where id = %s and profile_id = %s and status = 'in_progress'",
        (session_id, profile_id),
    ).fetchone()


def record_event(conn: psycopg.Connection, profile_id: UUID, session_id: UUID, event: EventRequest) -> bool:
    """Save one answer, update mastery and the resume point. False if the session is not open."""
    if not _open_session(conn, profile_id, session_id):
        return False
    conn.execute(
        """insert into session_events (session_id, profile_id, step, skill, question, answer, is_correct)
           values (%s, %s, %s, %s, %s, %s, %s)""",
        (session_id, profile_id, event.step, event.skill, event.question, event.answer, event.is_correct),
    )
    result = 1.0 if event.is_correct else 0.0
    conn.execute(
        """insert into skill_mastery (profile_id, skill, score, attempts, correct)
           values (%s, %s, 0.5 + %s * (%s - 0.5), 1, %s)
           on conflict (profile_id, skill) do update set
             score = skill_mastery.score + %s * (%s - skill_mastery.score),
             attempts = skill_mastery.attempts + 1,
             correct = skill_mastery.correct + %s,
             updated_at = now()""",
        (profile_id, event.skill, MASTERY_RATE, result, int(event.is_correct), MASTERY_RATE, result, int(event.is_correct)),
    )
    conn.execute(
        """update lesson_sessions set current_step = greatest(current_step, %s), updated_at = now()
           where id = %s""",
        (event.step + 1, session_id),
    )
    return True


def set_step(conn: psycopg.Connection, profile_id: UUID, session_id: UUID, step: int) -> bool:
    """Save where the child is in an unfinished lesson (also when they go back)."""
    row = conn.execute(
        """update lesson_sessions set current_step = %s, updated_at = now()
           where id = %s and profile_id = %s and status = 'in_progress' returning id""",
        (step, session_id, profile_id),
    ).fetchone()
    return row is not None


def complete(conn: psycopg.Connection, profile_id: UUID, session_id: UUID, summary: str) -> bool:
    row = conn.execute(
        """update lesson_sessions set status = 'completed', summary = %s, completed_at = now(), updated_at = now()
           where id = %s and profile_id = %s and status = 'in_progress' returning id""",
        (summary, session_id, profile_id),
    ).fetchone()
    return row is not None


def load_progress(conn: psycopg.Connection, profile: dict) -> Progress:
    """Everything the tutor needs to continue this child's learning. Read fresh on every call."""
    pid = profile["id"]
    open_row = conn.execute(
        "select id, lesson_id, current_step from lesson_sessions where profile_id = %s and status = 'in_progress'",
        (pid,),
    ).fetchone()
    completed = conn.execute(
        "select distinct lesson_id from lesson_sessions where profile_id = %s and status = 'completed' order by lesson_id",
        (pid,),
    ).fetchall()
    mastery = conn.execute(
        "select skill, score, attempts from skill_mastery where profile_id = %s order by score, skill", (pid,)
    ).fetchall()
    summaries = conn.execute(
        """select lesson_id, coalesce(summary, '') as summary, completed_at from lesson_sessions
           where profile_id = %s and status = 'completed' order by completed_at desc limit %s""",
        (pid, RECENT_SUMMARIES),
    ).fetchall()
    mistakes = conn.execute(
        """select skill, question, answer from session_events
           where profile_id = %s and not is_correct order by created_at desc limit %s""",
        (pid, RECENT_MISTAKES),
    ).fetchall()
    return Progress(
        profile={k: profile[k] for k in ("user_id", "parent_name", "child_name", "grade", "report_language")},
        in_progress=OpenSession(**open_row) if open_row else None,
        completed_lessons=[r["lesson_id"] for r in completed],
        mastery=[SkillMastery(**r) for r in mastery],
        weak_skills=[r["skill"] for r in mastery if r["score"] < WEAK_BELOW],
        recent_summaries=[SessionSummary(**r) for r in summaries],
        recent_mistakes=[Mistake(**r) for r in mistakes],
    )
