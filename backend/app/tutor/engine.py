"""Lesson logic: which item is current, the single retry, and checking the child's answer.

This is deliberately plain code (not AI) so Sakhi cannot skip ahead, loop on an item, or
accept a wrong answer: the AI only phrases what this module decides.
"""

import random
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, Field

from app.tutor.content import MODULES, Item, Module

Language = Literal["en", "hi", "te"]


class Snapshot(BaseModel):
    """An activity the child left half-way, so it can be resumed exactly where it stopped."""

    order: list[int] = Field(max_length=100)
    position: int = 0
    retry_used: bool = False
    waiting_ready: bool = False
    seen: list[int] = Field(default_factory=list, max_length=100)
    mode: Literal["ask", "spell", "blend", "demo", "understand"] = "ask"
    sub: int = Field(default=0, ge=0, le=20)
    demo_no: int = Field(default=0, ge=0, le=10)
    extra_used: bool = False
    letter_fix: bool = False


class TutorState(BaseModel):
    """The current session only. Nothing here is saved anywhere."""

    module: str | None = None
    order: list[int] = Field(default_factory=list, max_length=100)  # items of the current run, in order
    position: int = 0
    retry_used: bool = False
    waiting_ready: bool = False  # between two segments, waiting for "ready to continue?"
    seen: list[int] = Field(default_factory=list, max_length=100)  # pool items already used (random modules)
    struggled: list[str] = Field(default_factory=list, max_length=200)  # items needing practice this session
    language: Language = "en"  # language Sakhi is currently speaking
    # Where we are inside the current item. "ask": the child answers the item on the board. "spell"/"blend": a word
    # being read letter by letter, then as a whole. "demo"/"understand": maths shown with animated sticks first.
    mode: Literal["ask", "spell", "blend", "demo", "understand"] = "ask"
    sub: int = Field(default=0, ge=0, le=20)  # letter (spell) or animation step (demo) being shown
    demo_no: int = Field(default=0, ge=0, le=10)  # which demonstration (the last one is the extra example)
    extra_used: bool = False
    letter_fix: bool = False  # the current letter has already been corrected once
    paused: dict[str, Snapshot] = Field(default_factory=dict, max_length=12)  # activities left half-way


@dataclass(frozen=True)
class Outcome:
    kind: Literal["next", "retry", "segment_done", "complete"]
    correct: bool  # the child's answer was right
    missed: Item | None = None  # the item the child could not get even after the retry


# ---------------------------------------------------------------- state ---


def _inconsistent(state: TutorState, module: Module) -> bool:
    if state.mode in ("demo", "understand") and not module.demos:
        return True
    if state.mode in ("spell", "blend") and module.id != "english_words":
        return True
    if state.demo_no > len(module.demos) or (state.mode == "demo" and state.sub > 2):
        return True
    word = module.items[state.order[state.position]].answer if 0 <= state.position < len(state.order) else ""
    return state.mode == "spell" and state.sub >= len(word)


def _valid_paused(state: TutorState) -> dict[str, Snapshot]:
    kept = {}
    for module_id, snap in state.paused.items():
        if module_id in MODULES and _points_at_item(TutorState(module=module_id, **snap.model_dump())):
            kept[module_id] = snap
    return kept


def _points_at_item(state: TutorState) -> bool:
    module = MODULES[state.module or ""]
    size = len(module.items)
    last = len(state.order) if state.waiting_ready else len(state.order) - 1
    return (
        bool(state.order)
        and all(0 <= i < size for i in state.order + state.seen)
        and 0 <= state.position <= last
        and not _inconsistent(state, module)
    )


def sanitized(state: TutorState) -> TutorState:
    """Client-held state is untrusted: drop it if it does not point at a real item."""
    paused = _valid_paused(state)
    state = state.model_copy(update={"paused": paused})
    module = MODULES.get(state.module) if state.module else None
    if module is None:
        return TutorState(struggled=state.struggled, language=state.language, paused=paused)
    size = len(module.items)
    if _inconsistent(state, module):
        return TutorState(struggled=state.struggled, language=state.language, paused=paused)
    last = len(state.order) if state.waiting_ready else len(state.order) - 1  # the pause sits just past the end
    if any(not 0 <= i < size for i in state.order + state.seen) or not state.order or not 0 <= state.position <= last:
        return TutorState(struggled=state.struggled, language=state.language, paused=paused)
    return state


def current(state: TutorState) -> tuple[Module, Item] | None:
    if state.module is None:
        return None
    module = MODULES[state.module]
    return module, module.items[state.order[state.position]]


def _segment(module: Module, seen: list[int]) -> list[int]:
    if not module.segment:
        return list(range(len(module.items)))
    unseen = [i for i in range(len(module.items)) if i not in seen]
    if module.ordered:
        return unseen[: module.segment]
    return random.sample(unseen, min(module.segment, len(unseen)))


_FRESH_ITEM = {"mode": "ask", "sub": 0, "letter_fix": False}


def begin(state: TutorState, module_id: str) -> TutorState:
    module = MODULES[module_id]
    order = _segment(module, [])
    return state.model_copy(
        update={
            "module": module_id,
            "order": order,
            "position": 0,
            "retry_used": False,
            "waiting_ready": False,
            "seen": order if module.segment else [],
            **_FRESH_ITEM,
            "mode": "demo" if module.demos else "ask",
            "demo_no": 0,
            "extra_used": False,
        }
    )


def next_segment(state: TutorState) -> TutorState:
    module = MODULES[state.module or ""]
    order = _segment(module, state.seen)
    return state.model_copy(
        update={"order": order, "position": 0, "retry_used": False, "waiting_ready": False, "seen": state.seen + order, **_FRESH_ITEM}
    )


def stop(state: TutorState) -> TutorState:
    return state.model_copy(update={"module": None, "order": [], "position": 0, "retry_used": False, "waiting_ready": False, "seen": [], "demo_no": 0, "extra_used": False, **_FRESH_ITEM})


_SNAPSHOT_FIELDS = tuple(Snapshot.model_fields)


def pause(state: TutorState) -> TutorState:
    """Leave the current activity (if any) half-way, remembering where the child was."""
    if state.module is None:
        return state
    snap = Snapshot(**{name: getattr(state, name) for name in _SNAPSHOT_FIELDS})
    return stop(state.model_copy(update={"paused": {**state.paused, state.module: snap}}))


def resume(state: TutorState, module_id: str) -> TutorState | None:
    """Carry on a paused activity from where it stopped, or None if there is nothing valid to resume."""
    snap = state.paused.get(module_id)
    if snap is None:
        return None
    rest = {k: v for k, v in state.paused.items() if k != module_id}
    restored = state.model_copy(update={"module": module_id, "paused": rest, **snap.model_dump()})
    return restored if _points_at_item(restored) else None


def answer(state: TutorState, correct: bool) -> tuple[TutorState, Outcome]:
    """Apply the child's answer: praise and move on, allow exactly one retry, or note it and move on."""
    module, item = current(state)  # type: ignore[misc]
    if not correct and not state.retry_used:
        return state.model_copy(update={"retry_used": True}), Outcome("retry", correct=False)

    struggled = state.struggled if correct else [*state.struggled, f"{module.title}: {item.board}"]
    moved = state.model_copy(update={"position": state.position + 1, "retry_used": False, "struggled": struggled, **_FRESH_ITEM})
    missed = None if correct else item
    if moved.position < len(moved.order):
        return moved, Outcome("next", correct, missed)
    if module.segment and len(moved.seen) < len(module.items):
        return moved.model_copy(update={"waiting_ready": True}), Outcome("segment_done", correct, missed)
    return stop(moved), Outcome("complete", correct, missed)


# ------------------------------------------------- guided teaching steps ---


def start_spell(state: TutorState) -> TutorState:
    """The child could not read the word: go through its letters one at a time (the retry is the final blend)."""
    return state.model_copy(update={"mode": "spell", "sub": 0, "retry_used": True, "letter_fix": False})


def next_letter(state: TutorState, word: str) -> TutorState:
    if state.sub + 1 >= len(word):
        return state.model_copy(update={"mode": "blend", "sub": 0, "letter_fix": False})
    return state.model_copy(update={"sub": state.sub + 1, "letter_fix": False})


def mark_letter_fixed(state: TutorState) -> TutorState:
    return state.model_copy(update={"letter_fix": True})


def demo_pair(module: Module, state: TutorState) -> tuple[int, int]:
    pairs = module.demos + ((module.extra_demo,) if module.extra_demo else ())
    return pairs[min(state.demo_no, len(pairs) - 1)]


def demo_next(state: TutorState) -> TutorState:
    """The child took part in this step of the demonstration: show the next step, example or question."""
    module = MODULES[state.module or ""]
    if state.sub < 2:
        return state.model_copy(update={"sub": state.sub + 1})
    if state.demo_no >= len(module.demos):  # the extra example is finished: on to practice
        return state.model_copy(update={"mode": "ask", "sub": 0})
    if state.demo_no + 1 < len(module.demos):
        return state.model_copy(update={"demo_no": state.demo_no + 1, "sub": 0})
    return state.model_copy(update={"mode": "understand", "sub": 0})


def understood(state: TutorState, yes: bool) -> TutorState:
    module = MODULES[state.module or ""]
    if yes or state.extra_used or not module.extra_demo:
        return state.model_copy(update={"mode": "ask", "sub": 0})
    return state.model_copy(update={"mode": "demo", "sub": 0, "demo_no": len(module.demos), "extra_used": True})


_OPERANDS = re.compile(r"(\d+) ([+-]) (\d+)")


def operands(board_text: str) -> tuple[str, int, int] | None:
    found = _OPERANDS.match(board_text)
    return ("add" if found.group(2) == "+" else "sub", int(found.group(1)), int(found.group(3))) if found else None


def gave_no_answer(message: str) -> bool:
    """'I don't know' and the like: the child is asking for help rather than guessing."""
    tokens = _tokens(message)
    return not tokens or bool({"know", "idea", "sure", "hard", "difficult", "help"} & set(tokens)) or (
        "cant" in tokens
    )


def first_mismatch(target: str, message: str) -> tuple[str, int] | None:
    """For a wrong word: the word the child said (the closest one) and the first letter where it differs."""
    words = [t for t in _tokens(message) if t.isascii() and t.isalpha()]
    if not words:
        return None
    said = max(words, key=lambda w: SequenceMatcher(None, target, w).ratio())
    for i, letter in enumerate(target):
        if i >= len(said) or said[i] != letter:
            return said, i
    return said, len(target) - 1


def spoken_number(message: str) -> int | None:
    numbers = _numbers_in(_tokens(message))
    return numbers[-1] if numbers else None


def letter_said(message: str) -> str | None:
    """The letter the child named in one or two words, if they named one."""
    tokens = _tokens(message)
    if not tokens or len(tokens) > 2:
        return None
    for letter, names in _LETTER_NAMES.items():
        if any(token in names.split() for token in tokens):
            return letter
    return None


_TOPICS = {
    "alphabet": "alphabet alphabets abc abcs letters",
    "numbers": "numbers counting",
    "english_words": "words word",
    "english_sentences": "sentences sentence",
    "addition": "addition add plus",
    "subtraction": "subtraction subtract minus",
    "science_living": "living nonliving",
    "science_senses": "senses sense",
    "science_plants_animals": "plants plant animals animal",
    "science_weather": "weather seasons season",
}
_TOPIC_BY_WORD = {word: module for module, words in _TOPICS.items() for word in words.split()}
# A broad subject: Sakhi must ask which activity is meant.
_BROAD = {
    "maths": ("addition", "subtraction"), "math": ("addition", "subtraction"), "mathematics": ("addition", "subtraction"),
    "science": ("science_living", "science_senses", "science_plants_animals", "science_weather"),
    "english": ("english_words", "english_sentences", "alphabet"),
}
_ASKING = {"learn", "learning", "teach", "study", "practice", "practise", "switch", "instead", "change", "want", "wanna", "let", "lets", "read"}


def requested_module(message: str) -> str | tuple[str, ...] | None:
    """A module id when the child clearly asks to learn something, a tuple of ids when the subject is too broad
    (Sakhi should ask which one), or None. Only plain English requests are caught here; the AI judge catches the rest."""
    tokens = _tokens(message)
    if not 2 <= len(tokens) <= 14:
        return None
    asking = bool(_ASKING & set(tokens)) or ("do" in tokens and bool({"let", "lets", "we", "instead", "now"} & set(tokens)))
    if not asking:
        return None
    for token in tokens:
        if token in _TOPIC_BY_WORD:
            return _TOPIC_BY_WORD[token]
    for token in tokens:
        if token in _BROAD:
            return _BROAD[token]
    return None


_STOP_WORDS = {"stop", "quit", "finish", "enough"}
_REPEAT_WORDS = {"again", "repeat", "pardon", "what", "sorry"}


def quick_verdict(message: str) -> str | None:
    """Obvious one-word requests, so they need no AI call."""
    tokens = set(_tokens(message))
    if len(tokens) <= 2 and tokens & _STOP_WORDS:
        return "stop"
    if len(tokens) <= 2 and tokens & _REPEAT_WORDS:
        return "repeat"
    return None


def is_short_attempt(message: str) -> bool:
    """One or two words: an attempt at the answer rather than a remark or a question."""
    return len(_tokens(message)) <= 2


_STEPS = {"add": ("a", "b", "sum"), "sub": ("a", "cross", "left")}


def _visual(op: str, a: int, b: int, step: str) -> dict:
    return {"op": op, "a": a, "b": b, "step": step}


def board(state: TutorState) -> dict | None:
    """What the learning board shows: the current item (with sticks for maths), or nothing between items."""
    if state.waiting_ready or (shown := current(state)) is None:
        return None
    module, item = shown
    if module.demos and state.mode in ("demo", "understand"):
        a, b = demo_pair(module, state)
        op = "add" if module.id == "addition" else "sub"
        step = _STEPS[op][2 if state.mode == "understand" else state.sub]
        sign = "+" if op == "add" else "-"
        return {"kind": "math", "text": f"{a} {sign} {b} = ?", "visual": _visual(op, a, b, step)}
    result: dict = {"kind": module.board_kind, "text": item.board}
    if module.demos and state.retry_used and (found := operands(item.board)):
        result["visual"] = _visual(found[0], found[1], found[2], "explain")
    if state.mode == "spell":
        result["highlight"] = state.sub
    return result


# -------------------------------------------------------------- checking ---

_NON_LATIN = re.compile(r"[ऀ-ॿఀ-౿]")  # Devanagari or Telugu letters
_DIGITS = str.maketrans("०१२३४५६७८९౦౧౨౩౪౫౬౭౮౯", "01234567890123456789")

_ONES = {
    w: n
    for n, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
        "sixteen seventeen eighteen nineteen".split()
    )
}
_TENS = {w: 10 * n for n, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}

# How speech recognition may write each letter name.
_LETTER_NAMES = {
    "A": "a ay eh", "B": "b be bee", "C": "c see sea si", "D": "d dee di", "E": "e ee", "F": "f ef eff",
    "G": "g gee ji", "H": "h aitch ech age", "I": "i eye ai", "J": "j jay", "K": "k kay", "L": "l el ell",
    "M": "m em", "N": "n en", "O": "o oh owe", "P": "p pee pe", "Q": "q cue queue kyu", "R": "r are ar",
    "S": "s ess es", "T": "t tee tea", "U": "u you yu", "V": "v vee", "W": "w double-u doubleu",
    "X": "x ex", "Y": "y why wai", "Z": "z zee zed",
}
_NEGATED_LIVING = re.compile(r"\b(non living|nonliving|not living|not alive)\b")


def _normalize(text: str) -> str:
    text = text.translate(_DIGITS).lower().replace("-", " ").replace("'", "").replace("’", "")
    return re.sub(r"[^\w\s]", " ", text)


def _tokens(text: str) -> list[str]:
    return _normalize(text).split()


def _numbers_in(tokens: list[str]) -> list[int]:
    found: list[int] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.isdigit():
            found.append(int(token))
        elif token in _TENS:
            value = _TENS[token]
            if i + 1 < len(tokens) and 1 <= _ONES.get(tokens[i + 1], 0) <= 9:
                value += _ONES[tokens[i + 1]]
                i += 1
            found.append(value)
        elif token == "hundred":
            if found and found[-1] == 1:
                found[-1] = 100
            else:
                found.append(100)
        elif token in _ONES:
            found.append(_ONES[token])
        i += 1
    return found


def check_answer(module: Module, item: Item, message: str) -> bool | None:
    """True/False when the answer can be checked reliably here; None when the AI judge must decide
    (for example the child answered in Hindi or Telugu)."""
    tokens = _tokens(message)
    foreign = bool(_NON_LATIN.search(message))
    verdict: bool | None

    if module.check == "word":
        verdict = item.answer.lower() in tokens
    elif module.check == "sentence":
        target = _tokens(item.answer)
        blocks = SequenceMatcher(None, target, tokens, autojunk=False).get_matching_blocks()
        verdict = sum(block.size for block in blocks) / len(target) >= 0.75
    elif module.check == "letter":
        if len(tokens) > 2:  # "I do not know" would otherwise match the letter "I"
            return None
        names = _LETTER_NAMES[item.answer.upper()].split()
        verdict = any(name in tokens or name.replace("-", "") == "".join(tokens) for name in names)
    elif module.check == "number":
        numbers = _numbers_in(tokens)
        if not numbers:
            return None if foreign else False
        return numbers[-1] == int(item.answer)
    else:  # keywords
        text = " ".join(tokens)
        verdict = any(re.search(rf"\b{re.escape(k.replace('-', ' '))}\b", text) for k in item.accept)
        if verdict and item.answer == "living" and _NEGATED_LIVING.search(text):
            verdict = False

    if verdict:
        return True
    return None if foreign else False


# ---------------------------------------------------- sentence demonstration ---

LETTER_PAUSE, WORD_PAUSE, SENTENCE_PAUSE = 0.45, 0.9, 0.55  # seconds of silence after a letter / a word / a sentence word


def sentence_lesson(sentence: str) -> list[tuple[str, str, float]]:
    """The audio to play before the child reads: each word spelled letter by letter then said, in order, then the
    whole sentence slowly. Always English, whatever language Sakhi teaches in."""
    words = sentence.split()
    plan: list[tuple[str, str, float]] = []
    for word in words:
        spelled = [c for c in word if c.isalpha()]
        if not spelled:  # punctuation alone is never spelled
            continue
        plan += [(f"{letter.upper()}.", "en", LETTER_PAUSE) for letter in spelled]
        plan[-1] = (plan[-1][0], "en", 0.6)  # a little longer before the whole word
        plan.append(("".join(spelled), "en", WORD_PAUSE))
    plan += [(word, "en", SENTENCE_PAUSE) for word in words]  # keeps the punctuation, so the sentence ends naturally
    plan[-1] = (plan[-1][0], "en", 0.8)
    return plan
