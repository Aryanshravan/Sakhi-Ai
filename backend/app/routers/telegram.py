import secrets
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.auth import current_profile_row
from app.db import get_db
from app.integrations import telegram as bot
from app.security import hash_token

router = APIRouter(prefix="/telegram", tags=["telegram"])

TOKEN_MINUTES = 15


class TelegramStatus(BaseModel):
    configured: bool
    connected: bool


class LinkResponse(BaseModel):
    url: str


@router.get("/status", response_model=TelegramStatus)
def telegram_status(profile: dict = Depends(current_profile_row), conn: psycopg.Connection = Depends(get_db)):
    row = conn.execute("select telegram_chat_id from profiles where id = %s", (profile["id"],)).fetchone()
    return TelegramStatus(configured=bot.configured(), connected=bool(row and row["telegram_chat_id"]))


@router.post("/link", response_model=LinkResponse)
def create_link(profile: dict = Depends(current_profile_row), conn: psycopg.Connection = Depends(get_db)):
    """A one-time, short-lived token tied to this logged-in parent; the bot turns it into a chat link."""
    if not bot.configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Telegram is not set up on the server yet.")
    try:
        username = bot.bot_username()
    except bot.TelegramError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not reach Telegram. Please try again.")
    token = secrets.token_urlsafe(24)
    conn.execute("delete from telegram_link_tokens where profile_id = %s or expires_at < now()", (profile["id"],))
    conn.execute(
        "insert into telegram_link_tokens (token_hash, profile_id, expires_at) values (%s, %s, %s)",
        (hash_token(token), profile["id"], datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)),
    )
    return LinkResponse(url=f"https://t.me/{username}?start={token}")


@router.post("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(profile: dict = Depends(current_profile_row), conn: psycopg.Connection = Depends(get_db)):
    conn.execute("update profiles set telegram_chat_id = null, telegram_linked_at = null where id = %s", (profile["id"],))
    conn.execute("delete from telegram_link_tokens where profile_id = %s", (profile["id"],))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
