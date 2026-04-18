from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_name: str = Field(default="Ava", alias="BOT_NAME")
    confidence_threshold: float = Field(default=0.62, alias="CONFIDENCE_THRESHOLD", ge=0.0, le=1.0)
    negative_sentiment_escalation_turns: int = Field(
        default=3,
        alias="NEGATIVE_SENTIMENT_ESCALATION_TURNS",
        ge=1,
        le=20,
    )


settings = Settings()
