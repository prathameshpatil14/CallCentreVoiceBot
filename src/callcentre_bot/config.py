from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    bot_name: str
    confidence_threshold: float
    negative_sentiment_escalation_turns: int
    server_host: str
    server_port: int
    sqlite_path: str
    api_key: str
    max_request_bytes: int
    rate_limit_per_minute: int
    model_variant: str
    intent_threshold_sales: float
    intent_threshold_support: float
    intent_threshold_escalation: float
    intent_threshold_refund: float
    intent_threshold_upsell: float
    db_backend: str
    postgres_dsn: str
    retention_days: int
    archive_interval_seconds: int
    require_tls: bool
    valid_api_keys: tuple[str, ...]
    role_required_for_metrics: str
    max_clarifications: int
    max_retries_before_transfer: int
    drift_report_path: str
    drift_report_interval_seconds: int
    voice_engine_mode: str
    whisper_command: str
    piper_command: str
    piper_model_path: str
    voice_fallback_enabled: bool


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
    sqlite_path=os.getenv("SQLITE_PATH", "callcentre.db"),
    api_key=os.getenv("API_KEY", ""),
    max_request_bytes=_int_env("MAX_REQUEST_BYTES", 32768, 1024, 1024 * 1024),
    rate_limit_per_minute=_int_env("RATE_LIMIT_PER_MINUTE", 120, 1, 10000),
    model_variant=os.getenv("MODEL_VARIANT", "A").upper(),
    intent_threshold_sales=_float_env("INTENT_THRESHOLD_SALES", 0.62),
    intent_threshold_support=_float_env("INTENT_THRESHOLD_SUPPORT", 0.58),
    intent_threshold_escalation=_float_env("INTENT_THRESHOLD_ESCALATION", 0.50),
    intent_threshold_refund=_float_env("INTENT_THRESHOLD_REFUND", 0.60),
    intent_threshold_upsell=_float_env("INTENT_THRESHOLD_UPSELL", 0.62),
    db_backend=os.getenv("DB_BACKEND", "sqlite").strip().lower(),
    postgres_dsn=os.getenv("POSTGRES_DSN", "").strip(),
    retention_days=_int_env("RETENTION_DAYS", 30, 1, 3650),
    archive_interval_seconds=_int_env("ARCHIVE_INTERVAL_SECONDS", 3600, 60, 86400),
    require_tls=os.getenv("REQUIRE_TLS", "false").strip().lower() in {"1", "true", "yes"},
    valid_api_keys=tuple(part.strip() for part in os.getenv("API_KEYS", "").split(",") if part.strip()),
    role_required_for_metrics=os.getenv("ROLE_REQUIRED_FOR_METRICS", "agent").strip().lower(),
    max_clarifications=_int_env("MAX_CLARIFICATIONS", 2, 1, 10),
    max_retries_before_transfer=_int_env("MAX_RETRIES_BEFORE_TRANSFER", 2, 1, 10),
    drift_report_path=os.getenv("DRIFT_REPORT_PATH", "var/drift_weekly.jsonl").strip(),
    drift_report_interval_seconds=_int_env("DRIFT_REPORT_INTERVAL_SECONDS", 604800, 300, 1209600),
    voice_engine_mode=os.getenv("VOICE_ENGINE_MODE", "auto").strip().lower(),
    whisper_command=os.getenv("WHISPER_COMMAND", "whisper-cli").strip(),
    piper_command=os.getenv("PIPER_COMMAND", "piper").strip(),
    piper_model_path=os.getenv("PIPER_MODEL_PATH", "").strip(),
    voice_fallback_enabled=os.getenv("VOICE_FALLBACK_ENABLED", "true").strip().lower() in {"1", "true", "yes"},
)
