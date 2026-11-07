"""Receives /start <token> messages from parents by polling Telegram (no public URL or webhook needed)."""

import logging
import threading
import time

from app import reports
from app.config import settings
from app.db import pooled_connection
from app.integrations import telegram as bot
from app.security import hash_token

logger = logging.getLogger(__name__)

_WELCOME = (
    "Hi! I am Sakhi AI. To get your child's learning reports here, open Sakhi AI, choose Connect Telegram "
    "in the parent menu, and press Start from there."
)


def link_chat(token: str, chat_id: int) -> bool:
    """Bind the chat to the parent who created this token. The token is valid once and only for a short time; the
    chat id comes from Telegram itself, never from the website."""
    with pooled_connection() as conn:
        row = conn.execute(
            """update telegram_link_tokens set used_at = now()
               where token_hash = %s and used_at is null and expires_at > now() returning profile_id""",
            (hash_token(token),),
        ).fetchone()
        if row is None:
            conn.commit()
            return False
        conn.execute(
            "update profiles set telegram_chat_id = %s, telegram_linked_at = now() where id = %s", (chat_id, row["profile_id"])
        )
        conn.commit()
    threading.Thread(target=reports.resume_for_profile, args=(row["profile_id"],), daemon=True).start()
    return True


def _handle(update: dict) -> None:
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    text = (message.get("text") or "").strip()
    if chat.get("type") != "private" or not text.startswith("/start"):
        return
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(chat["id"], _WELCOME)
    elif link_chat(parts[1].strip(), chat["id"]):
        bot.send_message(chat["id"], "Connected! Sakhi AI will send your child's learning reports here as voice notes.")
    else:
        bot.send_message(chat["id"], "This link has expired or was already used. Please choose Connect Telegram in Sakhi AI again.")


def _poll() -> None:
    offset = 0
    while True:
        try:
            for update in bot.get_updates(offset):
                offset = update["update_id"] + 1
                try:
                    _handle(update)
                except Exception:
                    logger.exception("Could not handle a Telegram message")
        except bot.TelegramError as error:
            logger.warning("Telegram polling problem: %s", error)
            time.sleep(10)
        except Exception:
            logger.exception("Telegram polling crashed; retrying")
            time.sleep(10)


def start() -> None:
    if not bot.configured():
        logger.warning("TELEGRAM_BOT_TOKEN is not set: Telegram linking and delivery are off.")
        return
    threading.Thread(target=reports.resume_pending, name="report-resume", daemon=True).start()
    if not settings.telegram_polling:
        return
    try:
        bot.drop_webhook()
    except bot.TelegramError as error:
        logger.warning("Could not clear the Telegram webhook: %s", error)
    threading.Thread(target=_poll, name="telegram-poll", daemon=True).start()
