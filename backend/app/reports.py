"""The parent report: built from the saved learning records, spoken by the existing TTS, sent as a Telegram voice note.

Stages: pending -> generating -> ready -> sending -> sent. A failure stops at an explicit *_failed status and keeps
everything done so far, so a retry only repeats the stage that failed.
"""

import json
import logging
from datetime import date
from uuid import UUID

import httpx
import psycopg

from app.db import pooled_connection
from app.integrations import gemini, gnani
from app.integrations import telegram as bot

logger = logging.getLogger(__name__)

MAX_VOICE_SECONDS = 30.0
SAFE_VOICE_SECONDS = 28.0  # the limit we aim under, so measurement error can never push a note over 30 s
SHORTEN_ATTEMPTS = 3
# Words that fit in about 22 seconds of natural speech (measured with the TTS voices: English ~3.5 words per
# second, Hindi ~3.1, Telugu ~2.0).
WORD_BUDGET = {"en": 65, "hi": 58, "te": 40}
LANGUAGE_NAME = {"en": "English", "hi": "Hindi (Devanagari script)", "te": "Telugu (Telugu script)"}
_STALE_MINUTES = 4  # a stage that has been "running" longer than this was interrupted (for example a restart)

_RETRYABLE = ("pending", "generation_failed", "tts_failed", "delivery_failed", "telegram_not_connected")
_ACTIVE = ("generating", "ready", "sending")
TERMINAL = ("sent", *_RETRYABLE)

MESSAGES = {
    "sent": "The parent report was sent to Telegram.",
    "telegram_not_connected": "The session is saved and the report is ready, but Telegram is not connected yet. "
    "Connect it from the parent menu and the report can be sent.",
    "generation_failed": "The session is saved, but the report could not be written just now.",
    "tts_failed": "The session is saved and the report is written, but the voice note could not be created just now.",
    "delivery_failed": "The session is saved and the voice note is ready, but Telegram did not accept it just now.",
    "pending": "The report is still being prepared.",
    "generating": "The report is still being prepared.",
    "ready": "The report is still being prepared.",
    "sending": "The report is being sent.",
}

_voice_cache: dict[UUID, tuple[bytes, float, str]] = {}  # spoken audio waiting for delivery, so a retry need not redo it


class TtsFailed(Exception):
    pass


# ------------------------------------------------------------- the evidence ---


def summarize(rows: list[dict]) -> dict:
    """Statistics and the notable mistakes, computed only from what was recorded."""
    skills: dict[str, dict] = {}
    mistakes = []
    for row in rows:
        entry = skills.setdefault(row["skill"], {"correct_first_try": 0, "correct_after_help": 0, "needs_practice": 0, "unfinished": 0})
        key = {"correct": "correct_first_try", "correct_after_help": "correct_after_help", "needs_practice": "needs_practice", "open": "unfinished"}[row["outcome"]]
        entry[key] += 1
        if row["outcome"] in ("correct_after_help", "needs_practice") and len(mistakes) < 6:
            mistakes.append(
                {
                    "skill": row["skill"],
                    "target": row["question"],
                    "correct_answer": row["expected"],
                    "child_first_answer": row["first_answer"],
                    "attempts": row["attempts"],
                    "help_given": row["hint"],
                    "final": "got it right after guidance" if row["outcome"] == "correct_after_help" else "still needs practice",
                }
            )
    totals = {k: sum(s[k] for s in skills.values()) for k in ("correct_first_try", "correct_after_help", "needs_practice", "unfinished")}
    return {"questions_finished": sum(totals[k] for k in ("correct_first_try", "correct_after_help", "needs_practice")), **totals, "skills": skills, "mistakes": mistakes}


def _load(conn: psycopg.Connection, session_id: UUID) -> list[dict]:
    return conn.execute(
        """select skill, question, expected, first_answer, attempts, hint, outcome from session_events
           where session_id = %s order by id""",
        (session_id,),
    ).fetchall()


# --------------------------------------------------------------- the words ---

_REPORT_PROMPT = """You write the script of a short spoken voice note that a children's tutoring app (Sakhi AI) sends
to a child's parent after a learning session. The note is read aloud.
Write it in {language}. Use at most {words} words in total, in 4 or 5 short, natural, conversational sentences. In order:
what the child practised, the most important difficulty (merge repeated mistakes into one observation), whether the
child improved after guidance, and one useful suggestion for the parent.
Rules:
- Use ONLY facts in the DATA. Never invent mistakes, scores or praise. If there were no mistakes, say so plainly. If
  very little was done, say that plainly and keep the note very short.
- Do not exaggerate. Be warm, supportive and accurate. Never call the child weak, careless, slow or incapable.
- Speak to the parent, not to the child. Use the child's name; avoid he/she/him/her (the gender is not known).
- English learning words and maths expressions (for example "am" or "4 + 3") stay in English.
- Plain text only: no markdown, lists, emojis or headings. Write numbers as digits.
Return JSON only: {{"report": string}}"""

_SHORTEN_PROMPT = """Shorten this spoken voice note for a parent to at most {words} words. Keep it in the same language,
keep the most important point, keep it accurate and natural, and do not add anything new. Plain text only.
NOTE: {text}
Return JSON only: {{"report": string}}"""


def _gemini_report(system: str, text: str) -> str:
    result = gemini.generate_json(system, [{"role": "user", "parts": [{"text": text}]}])
    report = " ".join(str(result.get("report", "")).split())
    if not report:
        raise ValueError("empty report")
    return report


def generate_text(language: str, child: str, day: date, summary: dict) -> str:
    system = _REPORT_PROMPT.format(language=LANGUAGE_NAME[language], words=WORD_BUDGET[language])
    data = json.dumps({"child_name": child, "date": day.isoformat(), **summary}, ensure_ascii=False)
    return _gemini_report(system, "DATA: " + data)


def shorten_text(language: str, text: str, words: int) -> str:
    return _gemini_report(_SHORTEN_PROMPT.format(words=max(words, 8), text=text), "Shorten it.")


def fallback_text(language: str, child: str, summary: dict, minimal: bool = False) -> str:
    """A short report written from the numbers alone: used only if the AI's wording will not fit in the time limit."""
    done, right = summary["questions_finished"], summary["correct_first_try"] + summary["correct_after_help"]
    weak = [skill for skill, s in summary["skills"].items() if s["needs_practice"]]
    topics = ", ".join(summary["skills"]) or ""
    if language == "hi":
        if minimal:
            return f"{child} ने आज {right} सवाल सही किए।" if done else f"{child} ने आज कोई सवाल पूरा नहीं किया।"
        focus = f"{', '.join(weak)} पर थोड़ा और अभ्यास चाहिए।" if weak else "सब कुछ अच्छा रहा।"
        return (f"{child} ने आज {topics} का अभ्यास किया और {done} में से {right} सवाल सही किए। {focus} कृपया घर पर थोड़ा अभ्यास करवाएँ।"
                if done else f"{child} ने आज कोई सवाल पूरा नहीं किया। अगली बार थोड़ा और अभ्यास करवाएँ।")
    if language == "te":
        if minimal:
            return f"{child} ఈ రోజు {right} ప్రశ్నలకు సరిగ్గా చెప్పారు." if done else f"{child} ఈ రోజు ఏ ప్రశ్నా పూర్తి చేయలేదు."
        focus = f"{', '.join(weak)} పై ఇంకొంచెం సాధన కావాలి." if weak else "అంతా బాగా జరిగింది."
        return (f"{child} ఈ రోజు {topics} సాధన చేశారు. {done} ప్రశ్నలలో {right} సరిగ్గా చెప్పారు. {focus} ఇంట్లో కొంచెం సాధన చేయించండి."
                if done else f"{child} ఈ రోజు ఏ ప్రశ్నా పూర్తి చేయలేదు. తర్వాత కొంచెం సాధన చేయించండి.")
    if minimal:
        return f"{child} answered {right} questions correctly today." if done else f"{child} did not finish any questions today."
    focus = f"{', '.join(weak)} needs a little more practice." if weak else "Everything went well."
    return (f"{child} practised {topics} today and answered {right} of {done} questions correctly. {focus} Please practise together at home for a few minutes."
            if done else f"{child} did not finish any questions today. Please try a short session together soon.")


def make_voice(language: str, child: str, summary: dict, text: str) -> tuple[str, bytes, float]:
    """Speech for the report that is guaranteed to be under the time limit. Returns the text actually spoken."""
    for _ in range(SHORTEN_ATTEMPTS):
        if len(text.split()) > WORD_BUDGET[language] * 1.6:  # far too long to even send to the speech service
            try:
                text = shorten_text(language, text, WORD_BUDGET[language])
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                break
        audio = gnani.synthesize(text, language)
        seconds = gnani.mp3_seconds(audio)
        if 0 < seconds <= SAFE_VOICE_SECONDS:
            return text, audio, seconds
        if seconds <= 0:
            raise TtsFailed("The speech service returned unreadable audio.")
        target = int(len(text.split()) * (SAFE_VOICE_SECONDS - 3) / seconds)
        try:
            text = shorten_text(language, text, target)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            break
    for minimal in (False, True):  # the AI's wording would not fit: use plain wording built from the numbers
        text = fallback_text(language, child, summary, minimal)
        audio = gnani.synthesize(text, language)
        seconds = gnani.mp3_seconds(audio)
        if 0 < seconds <= SAFE_VOICE_SECONDS:
            return text, audio, seconds
    raise TtsFailed("Could not produce a voice note within 30 seconds.")


# ---------------------------------------------------------------- pipeline ---


def _set(conn: psycopg.Connection, session_id: UUID, **fields) -> None:
    columns = ", ".join(f"{name} = %s" for name in fields)
    conn.execute(f"update session_reports set {columns}, updated_at = now() where session_id = %s", (*fields.values(), session_id))  # noqa: S608
    conn.commit()


def run(conn: psycopg.Connection, session_id: UUID) -> dict:
    """Move a report as far along as possible. Safe to call repeatedly and concurrently: only one caller works on a
    report at a time, and a finished stage is never redone."""
    claimed = conn.execute(
        f"""update session_reports set claimed_at = now(), attempts = attempts + 1, updated_at = now(),
              status = case when report_text is null then 'generating' else 'sending' end, error = null
            where session_id = %s and (status = any(%s)
              or (status = any(%s) and claimed_at < now() - interval '{_STALE_MINUTES} minutes'))
            returning *""",
        (session_id, list(_RETRYABLE), list(_ACTIVE)),
    ).fetchone()
    conn.commit()
    if claimed is None:  # sent already, or another request is working on it
        return get(conn, session_id)

    info = conn.execute(
        """select p.child_name, p.telegram_chat_id, p.report_language, s.started_at
           from session_reports r join profiles p on p.id = r.profile_id join lesson_sessions s on s.id = r.session_id
           where r.session_id = %s""",
        (session_id,),
    ).fetchone()
    language, text = claimed["language"], claimed["report_text"]
    summary = summarize(_load(conn, session_id))

    if text is None:
        try:
            text = generate_text(language, info["child_name"], info["started_at"].date(), summary)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            logger.exception("Report generation failed")
            _set(conn, session_id, status="generation_failed", error="The AI could not write the report.")
            return get(conn, session_id)
        _set(conn, session_id, report_text=text, status="ready")  # saved before anything is sent

    if not info["telegram_chat_id"]:
        _set(conn, session_id, status="telegram_not_connected")
        return get(conn, session_id)

    _set(conn, session_id, status="sending")
    try:
        if session_id not in _voice_cache:
            text, audio, seconds = make_voice(language, info["child_name"], summary, text)
            _voice_cache[session_id] = (audio, seconds, text)
            _set(conn, session_id, report_text=text, audio_seconds=seconds)  # keep the text identical to what is spoken
        audio, seconds, text = _voice_cache[session_id]
    except Exception as error:
        logger.exception("Voice note failed")
        _set(conn, session_id, status="tts_failed", error=f"Speech: {type(error).__name__}")
        return get(conn, session_id)

    try:
        message_id = bot.send_voice(info["telegram_chat_id"], audio, f"{info['child_name']} · {info['started_at'].date()}\n\n{text}", seconds)
    except bot.TelegramError as error:
        logger.warning("Telegram delivery failed: %s", error)
        _set(conn, session_id, status="delivery_failed", error=str(error)[:300])
        return get(conn, session_id)
    _voice_cache.pop(session_id, None)  # delivered: nothing is kept
    conn.execute(
        "update session_reports set status = 'sent', telegram_message_id = %s, sent_at = now(), updated_at = now() where session_id = %s",
        (message_id, session_id),
    )
    conn.commit()
    return get(conn, session_id)


def get(conn: psycopg.Connection, session_id: UUID) -> dict:
    return conn.execute("select * from session_reports where session_id = %s", (session_id,)).fetchone()


def finalize(conn: psycopg.Connection, profile: dict, session_id: UUID) -> dict | None:
    """End the session (once) and bring its report forward. None if the session is not this profile's."""
    session = conn.execute(
        "select id, status from lesson_sessions where id = %s and profile_id = %s for update", (session_id, profile["id"])
    ).fetchone()
    if session is None:
        return None
    if session["status"] == "in_progress":
        conn.execute(
            "update lesson_sessions set status = 'completed', completed_at = now(), updated_at = now() where id = %s", (session_id,)
        )
    # The parent's saved report language is the only source for the report's language.
    conn.execute(
        """insert into session_reports (session_id, profile_id, language) values (%s, %s, %s)
           on conflict (session_id) do nothing""",
        (session_id, profile["id"], profile["report_language"]),
    )
    conn.commit()
    return run(conn, session_id)


def resume_pending() -> None:
    """Pick up reports that were interrupted (for example by a restart) or are waiting; run in the background."""
    try:
        with pooled_connection() as conn:
            ids = [
                r["session_id"]
                for r in conn.execute(
                    f"""select session_id from session_reports where status = 'pending'
                        or (status = any(%s) and claimed_at < now() - interval '{_STALE_MINUTES} minutes')""",
                    (list(_ACTIVE),),
                ).fetchall()
            ]
            conn.commit()
            for session_id in ids:
                run(conn, session_id)
    except Exception:
        logger.exception("Could not resume pending reports")


def resume_for_profile(profile_id: UUID) -> None:
    """After a parent connects Telegram, send the reports that were waiting for it."""
    try:
        with pooled_connection() as conn:
            ids = [
                r["session_id"]
                for r in conn.execute(
                    "select session_id from session_reports where profile_id = %s and status = 'telegram_not_connected'", (profile_id,)
                ).fetchall()
            ]
            conn.commit()
            for session_id in ids:
                run(conn, session_id)
    except Exception:
        logger.exception("Could not send waiting reports")
