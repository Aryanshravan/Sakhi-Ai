from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import telegram_bot
from app.routers import auth, learning, reports, telegram, tutor, voice_chat


@asynccontextmanager
async def lifespan(_: FastAPI):
    telegram_bot.start()  # parent linking, and finishing any report that was interrupted
    yield


app = FastAPI(title="Sakhi AI API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(learning.router)
app.include_router(voice_chat.router)
app.include_router(tutor.router)
app.include_router(reports.router)
app.include_router(telegram.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
