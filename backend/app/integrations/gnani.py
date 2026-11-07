import io
import re
import threading
import wave
import time

from gnani.stt import APIError as SttApiError
from gnani.stt import GnaniSTTClient
from gnani.tts import APIError as TtsApiError
from gnani.tts import AudioConfig, GnaniTTSClient

from app.config import settings

# Languages the child can speak, as short codes used throughout the app.
SUPPORTED_LANGUAGES = ("en", "hi", "te")

_STT_MODEL = "prisma-v3.0"
_TTS_MODEL = "timbre-v2.5"
# One voice per language, so the voice always matches the language being spoken.
_TTS_VOICES = {"en": ("en-IN", "Kaveri"), "hi": ("hi-IN", "Nalini"), "te": ("te-IN", "Suhana")}
_STT_CODES = {"en-IN": "en", "hi-IN": "hi", "te-IN": "te"}
_AUDIO = AudioConfig(sample_rate=24000, container="mp3", bitrate="64k")

# Gnani allows one active request per key at a time (otherwise HTTP 429), so
# calls wait for their turn here instead of failing.
_turn = threading.Lock()
_RATE_LIMITED = 429
_RETRIES = 2
_RETRY_DELAY_SECONDS = 1.0


def _with_retry(call):
    with _turn:
        for attempt in range(_RETRIES + 1):
            try:
                return call()
            except (SttApiError, TtsApiError) as error:
                if error.status_code != _RATE_LIMITED or attempt == _RETRIES:
                    raise
                time.sleep(_RETRY_DELAY_SECONDS)


def transcribe(audio_wav: bytes, english: bool = False, keyword: str | None = None) -> tuple[str, str | None]:
    """Speech to text. Returns the transcript and the detected language ("en", "hi", "te" or None).

    english=True is for answers to English lessons: auto-detection wrote short English words such as "am" in
    Telugu script, so the answer is transcribed as English, with the expected word as a hint (keyword).
    """

    def call() -> dict:
        audio = io.BytesIO(audio_wav)
        audio.name = "speech.wav"  # the SDK infers the audio format from the file name
        client = GnaniSTTClient(api_key=settings.gnani_api_key)
        if english:
            hints = {"keywords": [keyword]} if keyword else {}
            return client.transcribe(audio, language_code="en-IN", model=_STT_MODEL, **hints)
        # Auto-detect, but only among our three languages (short phrases were once mistaken for Bengali).
        return client.transcribe(
            audio, language_code="indic-auto", model=_STT_MODEL, language_candidates=list(_STT_CODES)
        )

    result = _with_retry(call)
    heard = _STT_CODES.get(result.get("detected_language_code"))
    return str(result.get("transcript", "")).strip(), "en" if english and heard is None else heard


def synthesize(text: str, language: str) -> bytes:
    """Text to speech in the given language ("en", "hi" or "te"). Returns MP3 bytes."""
    code, voice = _TTS_VOICES[language]
    return _with_retry(
        lambda: GnaniTTSClient(api_key=settings.gnani_api_key).synthesize(
            text, voice=voice, model=_TTS_MODEL, language=code, audio_config=_AUDIO
        )
    )


_WAV = AudioConfig(sample_rate=24000, container="wav")


def synthesize_mixed(text: str, language: str, english_words: list[str]) -> bytes:
    """Speech in `language`, except that the given English words are spoken by the English voice, so a Hindi or
    Telugu voice cannot mispronounce them (it read "am" as "em"). Returns WAV bytes."""
    words = sorted({w for w in english_words if w.strip()}, key=len, reverse=True)
    pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.IGNORECASE)
    pieces: list[tuple[str, str, float]] = []
    position = 0
    for found in pattern.finditer(text):
        pieces.append((text[position : found.start()], language, 0.0))
        pieces.append((found.group(0), "en", 0.0))
        position = found.end()
    pieces.append((text[position:], language, 0.0))
    return synthesize_sequence(pieces)


_piece_cache: dict[tuple[str, str], tuple[tuple[int, int, int], bytes]] = {}  # letters and words repeat a lot
_CACHE_LIMIT = 600


def _piece(text: str, language: str) -> tuple[tuple[int, int, int], bytes]:
    """(channels, sample width, rate) and PCM frames for one short phrase; the same phrase is only synthesized once."""
    key = (text, language)
    if key in _piece_cache:
        return _piece_cache[key]
    code, voice = _TTS_VOICES[language]
    audio = _with_retry(
        lambda: GnaniTTSClient(api_key=settings.gnani_api_key).synthesize(
            text, voice=voice, model=_TTS_MODEL, language=code, audio_config=_WAV
        )
    )
    with wave.open(io.BytesIO(audio)) as reader:
        piece = ((reader.getnchannels(), reader.getsampwidth(), reader.getframerate()), reader.readframes(reader.getnframes()))
    if len(text) <= 40 and len(_piece_cache) < _CACHE_LIMIT:
        _piece_cache[key] = piece
    return piece


def synthesize_sequence(segments: list[tuple[str, str, float]]) -> bytes:
    """Speech for (text, language, pause_after_seconds) segments, spoken strictly in the given order, each by its own
    language's voice, with the pauses built into the audio. One WAV, so it plays as one uninterrupted recording."""
    frames, params = [], None
    for text, language, pause in segments:
        if not any(char.isalnum() for char in text):
            continue
        params, pcm = _piece(text, language)
        frames.append(pcm)
        if pause > 0:
            frames.append(b"\x00" * (int(params[2] * pause) * params[1] * params[0]))
    out = io.BytesIO()
    with wave.open(out, "wb") as writer:
        writer.setnchannels(params[0])
        writer.setsampwidth(params[1])
        writer.setframerate(params[2])
        writer.writeframes(b"".join(frames))
    return out.getvalue()


_BITRATES = {3: (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320), 2: (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)}
_SAMPLE_RATES = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000), 0: (11025, 12000, 8000)}


def mp3_seconds(data: bytes) -> float:
    """Exact length of an MP3 in seconds, from its frame headers (so a length limit can be enforced)."""
    position = 10 + ((data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]) if data[:3] == b"ID3" else 0
    total = 0.0
    while position + 4 <= len(data):
        b1, b2, b3 = data[position + 1], data[position + 2], data[position]
        version, layer = (b1 >> 3) & 3, (b1 >> 1) & 3
        bitrate_index, rate_index = b2 >> 4, (b2 >> 2) & 3
        if b3 != 0xFF or (b1 & 0xE0) != 0xE0 or version == 1 or layer != 1 or bitrate_index in (0, 15) or rate_index == 3:
            position += 1
            continue
        mpeg1 = version == 3
        bitrate = _BITRATES[3 if mpeg1 else 2][bitrate_index] * 1000
        rate = _SAMPLE_RATES[version][rate_index]
        total += (1152 if mpeg1 else 576) / rate
        position += (144 if mpeg1 else 72) * bitrate // rate + ((b2 >> 1) & 1)
    return total
