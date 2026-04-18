from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    bot_name: str
    confidence_threshold: float
    negative_sentiment_escalation_turns: int
    server_host: str
    server_port: int



def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return max(0.0, min(1.0, parsed))



def _int_env(name: str, default: int, min_value: int, max_value: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(min_value, min(max_value, parsed))


settings = Settings(
    bot_name=os.getenv("BOT_NAME", "Ava"),
    confidence_threshold=_float_env("CONFIDENCE_THRESHOLD", 0.62),
    negative_sentiment_escalation_turns=_int_env("NEGATIVE_SENTIMENT_ESCALATION_TURNS", 3, 1, 20),
    server_host=os.getenv("SERVER_HOST", "0.0.0.0"),
    server_port=_int_env("SERVER_PORT", 8080, 1, 65535),
)
