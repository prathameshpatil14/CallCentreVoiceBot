from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Protocol
from uuid import UUID

from .models import SessionState

from .config import settings
from .storage import SqliteStore


class SessionPersistence(Protocol):
    def upsert_session(self, state: SessionState) -> None: ...
    def get_session(self, session_id: UUID) -> SessionState | None: ...
    def append_turn(
        self,
        *,
        session_id: object,
        request_id: str,
        user_text: str,
        bot_text: str,
        intent: str,
        sentiment: str,
        confidence: float,
    ) -> None: ...
    def archive_turns_older_than(self, cutoff_iso: str) -> int: ...


class PostgresStore:
    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("POSTGRES_DSN is required when DB_BACKEND=postgres")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise RuntimeError("psycopg is required for PostgreSQL backend") from exc

        self._psycopg = psycopg
        self._dict_row = dict_row
        self._conn = psycopg.connect(dsn, row_factory=dict_row)
        self._lock = Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        turns INTEGER NOT NULL,
                        consecutive_negative_turns INTEGER NOT NULL,
                        escalated INTEGER NOT NULL,
                        last_intent TEXT NOT NULL,
                        last_sentiment TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL,
                        customer_name TEXT,
                        account_type TEXT,
                        unresolved_issues TEXT,
                        campaign TEXT,
                        journey TEXT,
                        journey_state TEXT,
                        clarification_count INTEGER NOT NULL DEFAULT 0,
                        retry_count INTEGER NOT NULL DEFAULT 0,
                        account_id TEXT,
                        issue_summary TEXT
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS turns (
                        id SERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        request_id TEXT NOT NULL,
                        user_text TEXT NOT NULL,
                        bot_text TEXT NOT NULL,
                        intent TEXT NOT NULL,
                        sentiment TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        created_at_utc TEXT NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS turns_archive (
                        id SERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        request_id TEXT NOT NULL,
                        user_text TEXT NOT NULL,
                        bot_text TEXT NOT NULL,
                        intent TEXT NOT NULL,
                        sentiment TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        archived_at_utc TEXT NOT NULL
                    )
                    """
                )
            self._conn.commit()

    def upsert_session(self, state: SessionState) -> None:
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sessions(session_id, turns, consecutive_negative_turns, escalated, last_intent, last_sentiment, updated_at_utc, customer_name, account_type, unresolved_issues, campaign, journey, journey_state, clarification_count, retry_count, account_id, issue_summary)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(session_id) DO UPDATE SET
                      turns=EXCLUDED.turns,
                      consecutive_negative_turns=EXCLUDED.consecutive_negative_turns,
                      escalated=EXCLUDED.escalated,
                      last_intent=EXCLUDED.last_intent,
                      last_sentiment=EXCLUDED.last_sentiment,
                      updated_at_utc=EXCLUDED.updated_at_utc,
                      customer_name=EXCLUDED.customer_name,
                      account_type=EXCLUDED.account_type,
                      unresolved_issues=EXCLUDED.unresolved_issues,
                      campaign=EXCLUDED.campaign,
                      journey=EXCLUDED.journey,
                      journey_state=EXCLUDED.journey_state,
                      clarification_count=EXCLUDED.clarification_count,
                      retry_count=EXCLUDED.retry_count,
                      account_id=EXCLUDED.account_id,
                      issue_summary=EXCLUDED.issue_summary
                    """,
                    (
                        str(state.session_id),
                        state.turns,
                        state.consecutive_negative_turns,
                        1 if state.escalated else 0,
                        state.last_intent.value,
                        state.last_sentiment.value,
                        state.updated_at_utc.isoformat(),
                        state.customer_name,
                        state.account_type,
                        "|".join(state.unresolved_issues),
                        state.campaign,
                        state.journey.value,
                        state.journey_state.value,
                        state.clarification_count,
                        state.retry_count,
                        state.account_id,
                        state.issue_summary,
                    ),
                )
            self._conn.commit()

    def get_session(self, session_id: UUID) -> SessionState | None:
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute("SELECT * FROM sessions WHERE session_id = %s", (str(session_id),))
                row = cur.fetchone()
        if row is None:
            return None
        return SessionState.from_db_row(row)

    def append_turn(self, *, session_id: UUID, request_id: str, user_text: str, bot_text: str, intent: str, sentiment: str, confidence: float) -> None:
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO turns(session_id, request_id, user_text, bot_text, intent, sentiment, confidence, created_at_utc)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        str(session_id),
                        request_id,
                        user_text,
                        bot_text,
                        intent,
                        sentiment,
                        confidence,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
            self._conn.commit()

    def archive_turns_older_than(self, cutoff_iso: str) -> int:
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute("SELECT * FROM turns WHERE created_at_utc < %s", (cutoff_iso,))
                rows = cur.fetchall()
                for row in rows:
                    cur.execute(
                        """
                        INSERT INTO turns_archive(session_id, request_id, user_text, bot_text, intent, sentiment, confidence, created_at_utc, archived_at_utc)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            row["session_id"],
                            row["request_id"],
                            row["user_text"],
                            row["bot_text"],
                            row["intent"],
                            row["sentiment"],
                            row["confidence"],
                            row["created_at_utc"],
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                cur.execute("DELETE FROM turns WHERE created_at_utc < %s", (cutoff_iso,))
            self._conn.commit()
            return len(rows)


def create_store() -> SessionPersistence:
    if settings.db_backend == "postgres":
        return PostgresStore(settings.postgres_dsn)
    return SqliteStore(settings.sqlite_path)
