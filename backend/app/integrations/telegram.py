"""Telegram Bot API. The bot token never leaves this module: errors carry no URL, and request logging is silenced
because the token is part of every Bot API URL."""

import logging
from functools import lru_cache

import httpx

from app.config import settings

# httpx logs every request URL at INFO, which would put the bot token in the logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

CAPTION_LIMIT = 1024


class TelegramError(Exception):
    """A Telegram call failed. `permanent` means retrying cannot help (for example the user blocked the bot)."""

    def __init__(self, message: str, permanent: bool = False):
        super().__init__(message)
        self.permanent = permanent


def configured() -> bool:
    return bool(settings.telegram_bot_token)


def _call(method: str, *, data: dict | None = None, files: dict | None = None, timeout: float = 30) -> dict | list:
    if not settings.telegram_bot_token:
        raise TelegramError("Telegram is not configured.", permanent=True)
    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}", data=data, files=files, timeout=timeout
        )
        body = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise TelegramError(f"Could not reach Telegram ({type(error).__name__}).") from None
    if not body.get("ok"):
        code = body.get("error_code")
        raise TelegramError(f"Telegram refused the request ({code}): {body.get('description', '')}", permanent=code in (400, 401, 403))
    return body["result"]


@lru_cache
def bot_username() -> str:
    return _call("getMe")["username"]  # type: ignore[index]


def send_message(chat_id: int, text: str) -> int:
    return _call("sendMessage", data={"chat_id": chat_id, "text": text})["message_id"]  # type: ignore[index]


def send_voice(chat_id: int, mp3: bytes, caption: str, seconds: float) -> int:
    """A real Telegram voice note (sendVoice accepts MP3), with the written summary as its caption."""
    data = {"chat_id": chat_id, "duration": max(1, round(seconds))}
    if len(caption) <= CAPTION_LIMIT:
        data["caption"] = caption
    message = _call("sendVoice", data=data, files={"voice": ("report.mp3", mp3, "audio/mpeg")}, timeout=60)
    if len(caption) > CAPTION_LIMIT:
        send_message(chat_id, caption)
    return message["message_id"]  # type: ignore[index]


def get_updates(offset: int) -> list[dict]:
    return _call("getUpdates", data={"offset": offset, "timeout": 25, "allowed_updates": '["message"]'}, timeout=40)  # type: ignore[return-value]


def drop_webhook() -> None:
    """Updates are fetched by polling, which does not work while a webhook is set."""
    _call("deleteWebhook")
