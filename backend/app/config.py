from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        extra="ignore",
    )

    database_url: str
    gemini_api_key: str
    gnani_api_key: str
    telegram_bot_token: str | None = None
    telegram_polling: bool = True  # false: do not poll for /start messages (only one process may poll a bot)


settings = Settings()  # type: ignore[call-arg]
