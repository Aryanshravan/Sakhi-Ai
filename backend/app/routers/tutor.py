"""One tutoring turn: the engine decides what happens, Gemini only judges fuzzy answers and phrases Sakhi's words."""

import json
import logging
import re
from typing import Annotated, Any

import httpx
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints

from app.auth import current_profile_row
from app.db import pooled_connection
from app.session_log import Attempt, record_attempt
from app.integrations import gemini
from app.routers.voice_chat import Language, Segment, Turn
from app.tutor import engine
from app.tutor.content import MODULES, Item, Module
from app.tutor.engine import Outcome, TutorState

router = APIRouter(prefix="/tutor", tags=["tutor"], dependencies=[Depends(current_profile_row)])
logger = logging.getLogger(__name__)

_MENU = (
    "reading words, reading sentences, the alphabet, numbers 1 to 100, addition, subtraction, "
    "or science (living and non-living things, the five senses, plants and animals, weather and seasons)"
)


class TurnRequest(BaseModel):
    state: TutorState | None = None
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]
    preferred_language: Language
    heard_language: Language | None = None
    history: list[Turn] = Field(default_factory=list, max_length=40)
    session_id: UUID | None = None  # the open lesson session the answers are saved to


class TurnResponse(BaseModel):
    reply: str
    language: Language
    board: dict[str, Any] | None
    state: TutorState
    english_words: list[str] = Field(default_factory=list)  # to be pronounced by the English voice
    speech: list[Segment] | None = None  # when set, spoken in exactly this order (sentence teaching)


# The concept each activity practises, as named in the parent report.
SKILLS = {
    "english_words": "English word reading",
    "english_sentences": "English sentence reading",
    "alphabet": "Alphabet recognition",
    "numbers": "Number recognition",
    "addition": "Basic addition",
    "subtraction": "Basic subtraction",
}


def _attempt(module: Module, item: Item, message: str, correct: bool, hint: str | None, closes: bool) -> Attempt:
    return Attempt(
        topic=module.title,
        skill=SKILLS.get(module.id, module.title),
        question=item.board,
        expected=item.answer,
        answer=message,
        correct=correct,
        hint=hint,
        closes=closes,
    )


# --------------------------------------------------------------- prompts ---

_PERSONA = """You are Sakhi, a warm, patient tutor (a friendly husky) for a child in Grades 1 to 5, talking by voice.
You only teach simple English, Mathematics and Science. Use simple words and very short sentences. Be kind and
encouraging; never shame, scare or insult the child. Never give adult, violent, dangerous or otherwise unsuitable
content. No emojis, markdown or lists: your words are read aloud.
Teach like a real primary-school teacher: respond to what the child actually said, correct their specific mistake,
guide them step by step, and always wait for the child. Do not be robotic: never say flat things like "Incorrect",
"Correct, next question" or "No problem, let's move on". Do not gush; one short, specific, varied bit of
encouragement is enough.
Talk like a teacher in a real conversation: answer what the child actually said, give a hint that fits their specific
mistake (for example point to the letter or number they got wrong), ask only one question at a time, and do not
repeat the child's answer back to them or explain more than the moment needs. Vary your wording; avoid stock praise
such as "Great job", "Excellent" or "Wonderful" and avoid phrases like "I understand your response"."""

_LANGUAGE_RULES = """STRICT LANGUAGE RULES.
1. What is taught is always English. The words, sentences, letters, numbers, maths questions and science topics on
   the board stay in English, and you say the learning target itself in English (the word "cat", the number
   "seven", "two plus three equals five", "living things"). Never translate a target.
2. Numbers are always spoken as English words (one, two, three ... seven ... twenty), whether you are counting,
   naming a number the child is learning, giving an answer, or reading a sum. Never use Hindi or Telugu number names
   for them, and never write numbers in Hindi or Telugu script.
3. How you teach (greetings, instructions, questions, hints, corrections, encouragement, explanations) is in the
   child's chosen teaching language: {medium}
4. Write only in English (Roman) letters, never in Devanagari or Telugu script, even if the child's message below
   arrives in that script. Keep one teaching language for the whole conversation.
5. Sound like a real, warm teacher talking to a Grade 3 child: everyday spoken words, short sentences, no textbook
   language, no word-for-word translation from English. React to what the child actually said. Do not start two
   replies the same way, and do not overuse fillers such as "very good", "excellent", "chalo" or "sare".
Set "language" in your JSON to "{code}"."""

_MEDIUM = {
    "en": "English. Simple, natural spoken English.",
    "hi": "natural spoken Hindi written in English letters (Hinglish), as an Indian primary-school teacher talks. "
    'Style example (not a template): "Chalo, in dono groups ko add karte hain. Pehle group mein two marks hain, aur '
    'doosre group mein three marks. Ab sabko mila kar count karo." English school words (add, count, marks, number, '
    "word, letter, answer) stay in English because children learn them that way.",
    "te": "natural spoken Telugu written in English letters (Telglish), as a Telugu primary-school teacher talks. "
    'Style example (not a template): "Manam ee rendu groups ni add cheddam. First group lo two marks unnayi, second '
    'group lo three marks unnayi. Ippudu anni kalipi count cheyyi." English school words (add, count, marks, number, '
    "word, letter, answer) stay in English because children learn them that way.",
}

_ROUTER_PROMPT = (
    _PERSONA
    + """
The child is not in an activity yet. These are the activities you can teach:
{modules}
- If the child asks to learn or practise one of them, set "module" to its id and leave "reply" empty.
  If they only say "English" or "science" or "maths" without being specific, do not choose: set "module" to null and
  ask which one they want ({menu}).
- If they only greet you or chat, set "module" to null, reply in one or two short sentences, and ask what they would
  like to learn ({menu}).
- If they ask a genuine, simple school question, answer it in one or two simple sentences, then ask what they would
  like to learn.
- If they ask about anything else (games, videos, adult or scary things), kindly say you can help with learning, and
  ask what they would like to learn. Never discuss unsuitable topics.
"""
    + _LANGUAGE_RULES
    + """
Return JSON only: {{"module": string or null, "language": "en" | "hi" | "te", "reply": string}}"""
)

_JUDGE_PROMPT = """You judge a young child's spoken answer in a tutoring app.
Activity: {title}. The board shows: "{board}". The expected answer is: "{answer}".
The child said (speech-to-text; it may be English, Hindi or Telugu and may contain small recognition errors):
"{message}"
Choose ONE verdict:
- "correct": the child gave the expected answer (a different word for the same answer in another language is fine).
  For reading words, sentences and letters the child must really say the target; only accept spelling or
  transcription variants of it, never a different word.
- "incorrect": they tried to answer but it is wrong (a different word, letter, number or idea), or they said they
  do not know.
- "repeat": they asked to hear it again or did not understand.
- "question": they asked a genuine, simple learning question.
- "off_topic": they talked about something else (games, food, their day, a random sentence) and made no attempt
  at the answer. A single wrong word or number is "incorrect", not "off_topic". Asking to learn a different
  subject is "switch", not "off_topic".
- "stop": they want to stop or finish.
- "switch": they ask to learn or practise a different activity (for example "I want to learn numbers"); set
  "module" to the matching id from: {module_ids}.
Return JSON only: {{"verdict": string, "module": string or null}}"""

_DEMO_PROMPT = """A tutor is in the middle of teaching a young child. The child said (English, Hindi or Telugu): "{message}"
Choose ONE: "continue" (they are taking part: answering, guessing, saying "I don't know", or repeating after the tutor),
"off_topic" (talking about something unrelated), "question" (a genuine, simple learning question), "stop" (they want to
stop), or "switch" (they ask to learn something else; set "module" to one of: {module_ids}).
Return JSON only: {{"verdict": string, "module": string or null}}"""

_UNDERSTAND_PROMPT = """The tutor asked a child whether they understand how to add or subtract numbers using sticks.
The child said (English, Hindi or Telugu): "{message}"
Return JSON only: {{"understood": "yes" | "no" | "unclear"}}"""

_READY_PROMPT = """The tutor asked a child whether they are ready to continue with the next five items.
The child said (any of English, Hindi, Telugu): "{message}"
Return JSON only: {{"ready": "yes" | "no" | "unclear"}}"""

_PHRASE_PROMPT = (
    _PERSONA
    + """
Follow the DIRECTIVE exactly. Use short sentences: at most three normally, up to six only when you are counting
aloud or explaining with the sticks. Always end with the one question or request the directive asks for, and then stop
and wait for the child. Do not present any other item, do not move ahead on your own, and do not give a long lecture.
Use different wording from what you said recently:
{recent}

DIRECTIVE: {directive}

"""
    + _LANGUAGE_RULES
    + """
Return JSON only: {{"language": "en" | "hi" | "te", "reply": string}}"""
)


_LOCAL_SCRIPT = re.compile(r"[\u0900-\u097f\u0c00-\u0c7f]")  # Devanagari or Telugu letters


# For a new sentence the spoken reply is split in two around the audio demonstration of the sentence.
_SPLIT_REPLY = """
IMPORTANT: this reply is spoken in two parts, with a recorded demonstration of the sentence played between them. Return
JSON {"language": ..., "before": string, "after": string} instead of "reply". "before": at most two short sentences,
reacting to what the child just said or giving the praise or correction the DIRECTIVE asks for, followed by a short,
natural teacher's transition into the next sentence, worded differently each time and without gushing (if an activity
is just starting, say you will do it together). Never read, spell or mention the words of the new sentence. "after": exactly one
short sentence asking the child to read the whole sentence now (for example "Now you try! Can you read the whole
sentence?"), and nothing else."""


def _ask(system: str, text: str) -> dict:
    contents = [{"role": "user", "parts": [{"text": text}]}]
    result = gemini.generate_json(system, contents)
    if _LOCAL_SCRIPT.search(" ".join(str(result.get(key, "")) for key in ("reply", "before", "after"))):
        # Hindi/Telugu script is read wrongly by the text-to-speech and breaks the English learning targets: redo it.
        retry = system + "\nYour last answer used Hindi or Telugu script. Answer again using only English letters."
        result = gemini.generate_json(retry, contents)
    return result


def _language_rules(body: TurnRequest) -> dict[str, str]:
    """The language chosen on the learning screen is the only one Sakhi speaks; what was heard is ignored."""
    return {"medium": _MEDIUM[body.preferred_language], "code": body.preferred_language}


def _recent(body: TurnRequest) -> str:
    said = [t.text for t in body.history if t.role == "sakhi"][-2:]
    return "\n".join(f'- "{text[:200]}"' for text in said) or "- (nothing yet)"


# ------------------------------------------------------------ directives ---

_YES = {"yes", "yeah", "yep", "ok", "okay", "sure", "yup"}
_NO = {"no", "nope"}


def _present(state: TutorState) -> str:
    module, item = engine.current(state)  # type: ignore[misc]
    return f'The board now shows: "{item.board}". {module.ask}'


def _praise(outcome: Outcome) -> str:
    if outcome.correct:
        return "The child answered correctly: acknowledge it briefly and specifically, in fresh words. "
    missed = outcome.missed
    return (
        f'The child still found "{missed.board}" hard. Acknowledge their effort warmly and truthfully, tell them the '
        f'answer ("{missed.answer}": {missed.explain}) in one short sentence, and reassure them they will get better '
        "with practice. Do not say 'No problem'. "
        if missed
        else ""
    )


def _after_answer(state: TutorState, outcome: Outcome, module_title: str, item: Item) -> str:
    if outcome.kind == "retry":
        return (
            "The child's answer was not correct. Respond to what they actually said, gently, without scolding. Teach: "
            f'{item.explain} Then ask them to try once more; the board still shows "{item.board}".'
        )
    if outcome.kind == "next":
        return (
            f"{_praise(outcome)}Then lead into the next item with a short, natural teacher's transition of your own "
            f"(a few words, different each time, for example about trying another one). {_present(state)}"
        )
    if outcome.kind == "segment_done":
        return (
            f"{_praise(outcome)}They have finished this set of five. Say well done, then ask whether they are ready to "
            "continue with five more (yes or no). Do not present a new item yet."
        )
    return (
        f"{_praise(outcome)}They have finished the whole activity '{module_title}'. Congratulate them warmly, then ask "
        f"what they would like to learn next ({_MENU})."
    )


def _aside(state: TutorState, body: TurnRequest, verdict: str, again: str) -> tuple[TutorState, str]:
    """The child did not answer: they asked for a repeat, asked a question, wandered off, or want to stop."""
    if verdict in ("stop", "switch"):
        return engine.stop(state), f"The child wants to stop. Kindly agree and ask what they would like to learn next ({_MENU})."
    if verdict == "repeat":
        return state, f"The child did not catch that or asked to hear it again. Say it again, more simply. {again}"
    if verdict == "question":
        return state, (
            f'The child asked: "{body.message}". If it is a simple, child-friendly learning question, answer it in one or '
            f"two simple sentences; otherwise kindly say you cannot help with that. Then bring them back. {again}"
        )
    return state, (
        f'The child said something unrelated: "{body.message}". Reply in one very short, kind sentence without '
        f"discussing it. Then bring them back. {again}"
    )


# ----------------------------------------------------------- orchestration ---


def _start(state: TutorState, module_id: str) -> tuple[TutorState, str]:
    state = engine.begin(state, module_id)
    module = MODULES[module_id]
    if module.demos:
        return state, _demo_directive(state, module, None, first=True)
    intro = f"First say briefly: {module.intro} " if module.intro else ""
    return state, f"Start the activity '{module.title}': say you will do it together. {intro}Then: {_present(state)}"


def _judge(state: TutorState, body: TurnRequest) -> tuple[str, str | None]:
    """The verdict on what the child said while an item is on the board."""
    module, item = engine.current(state)  # type: ignore[misc]
    sure = engine.check_answer(module, item, body.message)
    if sure:
        return "correct", None
    if (quick := engine.quick_verdict(body.message)) is not None:
        return quick, None
    if sure is False and (engine.is_short_attempt(body.message) or engine.gave_no_answer(body.message)):
        return "incorrect", None  # a wrong word, letter or number, or "I don't know": no AI call needed
    prompt = _JUDGE_PROMPT.format(
        title=module.title,
        board=item.board,
        answer=item.answer,
        message=body.message,
        module_ids=", ".join(MODULES),
    )
    result = _ask(prompt, "Judge the child's answer.")
    verdict, module_id = str(result.get("verdict")), result.get("module")
    if verdict == "correct" and sure is False and module.check != "keywords":
        verdict = "incorrect"  # the exact check is authoritative for reading, letters and numbers
    if verdict not in {"correct", "incorrect", "repeat", "question", "off_topic", "stop", "switch"}:
        verdict = "incorrect"
    return verdict, module_id if module_id in MODULES else None


def _side_verdict(body: TurnRequest) -> tuple[str, str | None]:
    """During a demonstration or a letter-by-letter step any attempt is welcome: spot only the non-attempts."""
    if (quick := engine.quick_verdict(body.message)) is not None:
        return quick, None
    if len(body.message.split()) <= 3 or engine.spoken_number(body.message) is not None:
        return "continue", None
    result = _ask(_DEMO_PROMPT.format(message=body.message, module_ids=", ".join(MODULES)), "Decide.")
    verdict, module_id = str(result.get("verdict")), result.get("module")
    if verdict not in {"continue", "off_topic", "question", "stop", "switch"}:
        verdict = "continue"
    return verdict, module_id if module_id in MODULES else None


# --- switching topics and resuming a paused activity ---

_SWITCH_LEAD = "The child asked to learn this now: agree warmly and naturally in a few words, then "


def _resume_directive(state: TutorState) -> str:
    """Pick up a paused activity exactly where the child left it."""
    module, item = engine.current(state)  # type: ignore[misc]
    if state.waiting_ready:
        return "carry on with their earlier activity: they had finished a set, so ask whether they are ready to continue (yes or no)."
    if state.mode in ("demo", "understand"):
        if state.mode == "understand":
            return "carry on with the earlier activity: ask if they understand how we do it with sticks (yes or no)."
        return "carry on with the earlier activity, repeating the current example. " + _demo_directive(state, module, None)
    if state.mode == "spell":
        return "carry on with the earlier word. " + _word_guide(item.answer, state, first=False)
    if state.mode == "blend":
        return "carry on with the earlier word. " + _word_guide(item.answer, state, first=False)
    return f"carry on with the earlier activity exactly where they stopped. {_present(state)}"


def _switch(state: TutorState, module_id: str) -> tuple[TutorState, str]:
    """Pause whatever is running (it can be resumed later) and begin or resume the requested activity."""
    paused = engine.pause(state)
    resumed = engine.resume(paused, module_id)
    if resumed is not None:
        return resumed, _SWITCH_LEAD + _resume_directive(resumed)
    new, directive = _start(paused, module_id)
    return new, _SWITCH_LEAD + "begin it. " + directive


def _which_one(state: TutorState, options: tuple[str, ...]) -> tuple[TutorState, str]:
    names = ", ".join(MODULES[m].title for m in options)
    return state, (
        f"The child wants to learn something, but it could be any of: {names}. Do not start anything. Ask ONE short "
        "question which of these they would like. Name them in English."
    )


# --- word reading: letter by letter, then the whole word ---


def _word_guide(word: str, state: TutorState, first: bool) -> str:
    """Directive for the highlighted letter (mode 'spell') or for blending the whole word (mode 'blend')."""
    if state.mode == "blend":
        sounds = "-".join(word.upper())
        return (
            f"Praise their effort briefly. Now put the sounds together: say them slowly, {sounds}, and then the whole "
            f'word "{word}". Ask the child to try reading the whole word. The board shows "{word}".'
        )
    letter = word[state.sub].upper()
    if first:
        return (
            f'The child could not read "{word}". Do not just tell them the word. Say you will read it together, '
            f"slowly. The board highlights the first letter. Tell them: this is {letter}. Ask them to say {letter}."
        )
    return (
        "Respond kindly to what they said. The board now highlights the next letter. "
        f"Tell them: this is {letter}. Ask them to say {letter}."
    )


def _wrong_word_directive(word: str, message: str) -> str:
    said, i = engine.first_mismatch(word, message)  # type: ignore[misc]
    where = ("first", "second", "third", "last")[min(i, 3)]
    mine = word[i].upper()
    theirs = f'They said "{said[i].upper()}" there.' if i < len(said) else "They left that letter out."
    return (
        f'The child read "{said}" instead of "{word}". Be specific and gentle: tell them what they said, point to the '
        f'{where} letter ("{mine}") and explain that it is {mine}, not what they said. {theirs} Then say the word '
        f'slowly, sound by sound, "{"-".join(word.upper())}, {word}", and ask them to try reading the whole word '
        "again. The board still shows the word."
    )


def _decide_spell(state: TutorState, body: TurnRequest, item: Item) -> tuple[TutorState, str]:
    verdict, switch_to = _side_verdict(body)
    if verdict == "switch" and switch_to:
        return _switch(state, switch_to)
    if verdict != "continue":
        return _aside(state, body, verdict, "Then ask again about the highlighted letter.")
    word = item.answer
    letter = word[state.sub].upper()
    named = engine.letter_said(body.message)
    if named and named != letter and not state.letter_fix:
        return engine.mark_letter_fixed(state), (
            f'The child said "{named}" but the highlighted letter is {letter}. Kindly tell them this letter is '
            f"{letter}, say it clearly, and ask them to say {letter} once more."
        )
    new = engine.next_letter(state, word)
    return new, _word_guide(word, new, first=False)


# --- maths: teaching with animated sticks ---


def _expected_note(message: str, expected: int, what: str) -> str:
    said = engine.spoken_number(message)
    if said == expected:
        return f"The child said {said}, which is right: tell them so briefly. "
    if said is not None:
        return f"The child said {said}, but {what} is {expected}: gently correct them. "
    return f"React naturally to what the child said. The right number for {what} is {expected}. "


def _demo_directive(state: TutorState, module: Module, body: TurnRequest | None, first: bool = False) -> str:
    a, b = engine.demo_pair(module, state)
    adding = module.id == "addition"
    msg = body.message if body else ""
    total = a + b if adding else a - b
    intro = ""
    if first:
        action = "add numbers" if adding else "take numbers away"
        intro = f"Say warmly that today you will learn to {action} using sticks, and ask them to watch the board. "
    elif state.sub == 0:
        intro = "Say well done, and show a new example. "
    if state.sub == 0:
        if adding:
            return (
                f'{intro}The board shows "{a} + {b} = ?" and {a} sticks are being drawn one at a time. Count the '
                f"sticks with the child, one to {a}, slowly. Then ask: how many sticks do you see?"
            )
        return (
            f'{intro}The board shows "{a} - {b} = ?" and {a} sticks are being drawn one at a time. Count them aloud, '
            f"one to {a}. Then ask: how many sticks do we have before we take any away?"
        )
    if state.sub == 1:
        note = _expected_note(msg, a, "the number of sticks")
        if adding:
            return (
                f"{note}Now {b} more sticks are being drawn, in a different colour. Count them aloud, one to {b}. "
                "Then ask: how many sticks do you think we have altogether?"
            )
        return (
            f"{note}Now {b} of the sticks are being crossed out. Count the crossed ones aloud, one to {b}. Then ask: "
            "how many sticks do you think are left?"
        )
    note = _expected_note(msg, total, "the total" if adding else "what is left")
    if adding:
        return (
            f"{note}The two groups are being pushed together. Count all the sticks aloud, one to {total}. Say: {a} "
            f"plus {b} equals {total}. Then ask the child to say it with you: {a} plus {b} equals...?"
        )
    return (
        f"{note}The crossed-out sticks go away. Count the sticks that are left aloud, one to {total}. Say: {a} minus "
        f"{b} equals {total}. Then ask the child to say it with you: {a} minus {b} equals...?"
    )


def _decide_demo(state: TutorState, body: TurnRequest, module: Module) -> tuple[TutorState, str]:
    verb = "add" if module.id == "addition" else "subtract"
    if state.mode == "understand":
        tokens = set(body.message.lower().replace(".", " ").replace(",", " ").split())
        if tokens & _YES:
            answer = "yes"
        elif tokens & _NO:
            answer = "no"
        else:
            answer = _ask(_UNDERSTAND_PROMPT.format(message=body.message), "Decide.").get("understood")
        if answer == "yes":
            new = engine.understood(state, True)
            return new, f"Say you are happy they understand. Now they will try on their own. {_present(new)}"
        if answer == "no":
            new = engine.understood(state, False)
            if new.mode == "demo":
                return new, "Say that is fine, and that you will look at one more example together. " + _demo_directive(new, module, None)
            return new, f"Encourage them kindly. They will try on their own and you will help. {_present(new)}"
        return state, f"Ask again, simply, whether they understand how we {verb} numbers with sticks (yes or no)."

    verdict, switch_to = _side_verdict(body)
    if verdict == "switch" and switch_to:
        return _switch(state, switch_to)
    if verdict != "continue":
        return _aside(state, body, verdict, "Then repeat your last question about the sticks on the board.")
    new = engine.demo_next(state)
    if new.mode == "understand":
        return new, (
            "Praise them for saying it with you. "
            f"Then ask: now, do you understand how we {verb} these numbers together? (yes or no)"
        )
    if new.mode == "ask":  # the extra example is done: practice begins
        return new, f"Say well done. Now they will try on their own. {_present(new)}"
    return new, _demo_directive(new, module, body)


def _decide(state: TutorState, body: TurnRequest, log: list[Attempt]) -> tuple[TutorState, str | None, dict | None]:
    """Returns the new state and the directive for Sakhi, or (state, None, routed_reply) for plain chat."""
    wanted = engine.requested_module(body.message)
    if isinstance(wanted, tuple):
        new_state, directive = _which_one(state, wanted)
        return new_state, directive, None
    if wanted and wanted != state.module:
        new_state, directive = _switch(state, wanted)
        return new_state, directive, None

    if state.module is None:
        system = _ROUTER_PROMPT.format(
            modules="\n".join(f"- {m.id}: {m.title}" for m in MODULES.values()),
            menu=_MENU,
            **_language_rules(body),
        )
        routed = _ask(system, body.message)
        module_id = routed.get("module")
        if module_id in MODULES:
            new_state, directive = _switch(state, module_id)
            return new_state, directive, None
        return state, None, routed

    if state.waiting_ready:
        ready = _ask(_READY_PROMPT.format(message=body.message), "Decide.").get("ready")
        if ready == "yes":
            new_state = engine.next_segment(state)
            return new_state, f"Say something short to carry on. {_present(new_state)}", None
        if ready == "no":
            return engine.stop(state), f"The child does not want to continue. Kindly agree and ask what they would like to learn next ({_MENU}).", None
        return state, "Ask again, in a simple way, whether they are ready to continue. They can say yes or no.", None

    module, item = engine.current(state)  # type: ignore[misc]
    if state.mode in ("demo", "understand"):
        new_state, directive = _decide_demo(state, body, module)
        return new_state, directive, None
    if state.mode == "spell":
        new_state, directive = _decide_spell(state, body, item)
        return new_state, directive, None

    verdict, switch_to = _judge(state, body)
    if verdict in ("correct", "incorrect"):
        if verdict == "incorrect" and module.id == "english_words" and not state.retry_used:
            mismatch = engine.first_mismatch(item.answer, body.message)
            if engine.gave_no_answer(body.message) or mismatch is None:
                new_state = engine.start_spell(state)  # could not read it: go through the letters
                log.append(_attempt(module, item, body.message, False, "Sounded the word out letter by letter.", closes=False))
                return new_state, _word_guide(item.answer, new_state, first=True), None
            new_state, _ = engine.answer(state, False)  # read a different word: correct that specific mistake
            log.append(_attempt(module, item, body.message, False, f"Pointed out the letter that differs from what was read ({item.explain})", closes=False))
            return new_state, _wrong_word_directive(item.answer, body.message), None
        new_state, outcome = engine.answer(state, verdict == "correct")
        hint = item.explain if outcome.kind == "retry" else None
        log.append(_attempt(module, item, body.message, verdict == "correct", hint, closes=outcome.kind != "retry"))
        return new_state, _after_answer(new_state, outcome, module.title, item), None
    if verdict == "switch" and switch_to:
        new_state, directive = _switch(state, switch_to)
        return new_state, directive, None
    again = f'The board still shows "{item.board}"; ask the child to answer it. {module.ask}'
    new_state, directive = _aside(state, body, verdict, again)
    return new_state, directive, None


def _save_attempts(profile_id: UUID, session_id: UUID, attempts: list[Attempt]) -> None:
    with pooled_connection() as conn:
        for attempt in attempts:
            record_attempt(conn, profile_id, session_id, attempt)


@router.post("/turn", response_model=TurnResponse)
def turn(
    body: TurnRequest,
    background: BackgroundTasks,
    profile: dict = Depends(current_profile_row),
):
    state = engine.sanitized(body.state) if body.state else TutorState(language=body.preferred_language)
    log: list[Attempt] = []
    speech: list[Segment] | None = None
    try:
        new_state, directive, routed = _decide(state, body, log)
        # A new sentence has just been put on the board: it is taught by audio before the child is asked to read it.
        presenting = (
            new_state.module == "english_sentences"
            and new_state.mode == "ask"
            and not new_state.waiting_ready
            and (state.module != new_state.module or state.position != new_state.position or state.waiting_ready)
        )
        if directive is None:  # plain conversation with no activity running
            reply = str((routed or {}).get("reply", "")).strip()
        elif presenting:
            system = _PHRASE_PROMPT.format(directive=directive, recent=_recent(body), **_language_rules(body)) + _SPLIT_REPLY
            parts = _ask(system, f'The child just said: "{body.message}"')
            before, after = str(parts.get("before", "")).strip(), str(parts.get("after", "")).strip()
            reply = f"{before} {after}".strip()
            if not after:
                raise ValueError("empty reply")
            sentence = engine.current(new_state)[1].board  # type: ignore[index]
            plan = [(before, body.preferred_language, 0.4)] if before else []
            plan += engine.sentence_lesson(sentence) + [(after, body.preferred_language, 0.0)]
            speech = [Segment(text=t, language=lang, pause=pause) for t, lang, pause in plan]
        else:
            system = _PHRASE_PROMPT.format(directive=directive, recent=_recent(body), **_language_rules(body))
            reply = str(_ask(system, f'The child just said: "{body.message}"').get("reply", "")).strip()
        if not reply:
            raise ValueError("empty reply")
    except (httpx.HTTPError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        logger.exception("Tutor turn failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Sakhi could not think of an answer just now.")

    if body.session_id and log:  # save the evidence once Sakhi's answer is on its way, so saving never delays it
        background.add_task(_save_attempts, profile["id"], body.session_id, log)

    language = body.preferred_language  # speech (TTS) always uses the selected language
    new_state = new_state.model_copy(update={"language": language})
    board = engine.board(new_state)
    target = board["text"] if board and board["kind"] == "word" and board["text"].isalpha() else None
    return TurnResponse(
        reply=reply,
        language=language,
        board=board,
        state=new_state,
        english_words=[target] if target else [],
        speech=speech,
    )
