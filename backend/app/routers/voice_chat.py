import json
import logging
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field, StringConstraints

from app.auth import current_profile_row
from app.integrations import gemini, gnani

# Login is required: these endpoints call paid third-party APIs.
router = APIRouter(prefix="/voice-chat", tags=["voice-chat"], dependencies=[Depends(current_profile_row)])
logger = logging.getLogger(__name__)

Language = Literal["en", "hi", "te"]
LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "te": "Telugu"}
MAX_AUDIO_BYTES = 2_000_000
MAX_HISTORY_TURNS = 10
# One or two words (such as "Hi Sakhi") are not enough to tell the language reliably.
SHORT_MESSAGE_WORDS = 2


class Turn(BaseModel):
    role: Literal["user", "sakhi"]
    text: Annotated[str, StringConstraints(max_length=800)]


class ReplyRequest(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]
    history: list[Turn] = Field(default_factory=list, max_length=40)
    preferred_language: Language
    heard_language: Language | None = None


class Reply(BaseModel):
    reply: str
    language: Language


class Transcript(BaseModel):
    text: str
    language: Language | None


class Segment(BaseModel):
    """One piece of an ordered speech plan: what to say, in which language's voice, and the pause after it."""

    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
    language: Language
    pause: Annotated[float, Field(ge=0, le=3)] = 0.0


class SpeakRequest(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]
    language: Language
    # English words in the text that must be pronounced by the English voice, whatever language Sakhi speaks.
    segments: list[Segment] = Field(default_factory=list, max_length=80)  # when given, spoken in this order instead
    english_words: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]] = Field(
        default_factory=list, max_length=20
    )


_SYSTEM_PROMPT = """You are Sakhi, a warm, cheerful voice companion chatting with a child.
This is a spoken conversation: your reply will be read aloud, so keep it to one to three short, natural
sentences in simple words. No emojis, no markdown, no lists, no stage directions.
Answer what the child actually said, and remember what was said earlier in the conversation.

Language rules (very important):
- The child can speak English, Hindi or Telugu. The child's preferred language is {preferred}.
- Work out which language the child's LATEST message is mainly in, and reply in that same language.
  If they mix languages, use the one they use most. This overrides the preferred language: for example,
  if the preferred language is Telugu but the child speaks English, answer in English.
- Only if you truly cannot tell the language, use the preferred language. Speech recognition often writes a
  short English greeting or name in Hindi/Telugu letters (for example "हायसाकी" for "Hi Sakhi"); a very short
  message like that is NOT enough evidence of a language, so use the preferred language.
- Write Hindi in Devanagari script and Telugu in Telugu script (never in English letters).
{hint}
Return JSON only: {{"language": "en" | "hi" | "te", "reply": string}} where "language" is the language of your reply."""


def _contents(history: list[Turn], message: str) -> list[dict]:
    """Gemini conversation: recent turns, alternating user/model, ending with the new message."""
    turns = [*history[-MAX_HISTORY_TURNS:], Turn(role="user", text=message)]
    contents: list[dict] = []
    for turn in turns:
        role = "user" if turn.role == "user" else "model"
        if contents and contents[-1]["role"] == role:  # e.g. a reply failed earlier: merge, keep alternating
            contents[-1]["parts"][0]["text"] += "\n" + turn.text
        else:
            contents.append({"role": role, "parts": [{"text": turn.text}]})
    while contents and contents[0]["role"] != "user":
        contents.pop(0)
    return contents


@router.post("/transcribe", response_model=Transcript)
async def transcribe(request: Request, english: bool = False, keyword: str | None = Query(None, max_length=30)):
    """Body: a WAV recording of the child speaking. Returns the text and the detected language.
    english=true: the child is answering an English lesson, so transcribe as English (keyword: the expected word)."""
    audio = await request.body()
    if not audio or len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Audio is missing or too long.")
    try:
        text, language = gnani.transcribe(audio, english, keyword)
    except Exception:
        logger.exception("Speech-to-text failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not understand the audio.")
    return Transcript(text=text, language=language)


@router.post("/reply", response_model=Reply)
def reply(body: ReplyRequest):
    if len(body.message.split()) <= SHORT_MESSAGE_WORDS:
        hint = (
            "The latest message is only one or two words, so its language is uncertain. "
            f"Reply in the preferred language ({LANGUAGE_NAMES[body.preferred_language]}).\n"
        )
    elif body.heard_language:
        hint = (
            f"Speech recognition guessed the child spoke {LANGUAGE_NAMES[body.heard_language]} (it can be wrong; "
            "trust the text itself).\n"
        )
    else:
        hint = ""
    system = _SYSTEM_PROMPT.format(preferred=LANGUAGE_NAMES[body.preferred_language], hint=hint)
    try:
        result = gemini.generate_json(system, _contents(body.history, body.message))
        text = str(result["reply"]).strip()
        if not text:
            raise ValueError("empty reply")
    except (httpx.HTTPError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        logger.exception("Gemini request failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Sakhi could not think of an answer just now.")
    language = result.get("language")
    return Reply(reply=text, language=language if language in gnani.SUPPORTED_LANGUAGES else body.preferred_language)


@router.post("/speak")
def speak(body: SpeakRequest):
    try:
        if body.segments:
            plan = [(seg.text, seg.language, seg.pause) for seg in body.segments]
            return Response(content=gnani.synthesize_sequence(plan), media_type="audio/wav")
        if body.english_words and body.language != "en":
            return Response(content=gnani.synthesize_mixed(body.text, body.language, body.english_words), media_type="audio/wav")
        audio = gnani.synthesize(body.text, body.language)
    except Exception:
        logger.exception("Text-to-speech failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not generate speech.")
    return Response(content=audio, media_type="audio/mpeg")
