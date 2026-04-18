import sqlite3
from datetime import datetime, timezone
from threading import Lock
from uuid import UUID

from .models import SessionState


class SqliteStore:
    def __init__(self, db_path: str) -> None:
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self.lock:
            self.conn.execute(
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
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS turns_archive (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            self._ensure_columns()
            self.conn.commit()

    def _ensure_columns(self) -> None:
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(sessions)")}
        migrations = [
            ("journey", "ALTER TABLE sessions ADD COLUMN journey TEXT"),
            ("journey_state", "ALTER TABLE sessions ADD COLUMN journey_state TEXT"),
            (
                "clarification_count",
                "ALTER TABLE sessions ADD COLUMN clarification_count INTEGER NOT NULL DEFAULT 0",
            ),
            ("retry_count", "ALTER TABLE sessions ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0"),
            ("account_id", "ALTER TABLE sessions ADD COLUMN account_id TEXT"),
            ("issue_summary", "ALTER TABLE sessions ADD COLUMN issue_summary TEXT"),
        ]
        for column, statement in migrations:
            if column not in columns:
                self.conn.execute(statement)

    def upsert_session(self, state: SessionState) -> None:
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO sessions(session_id, turns, consecutive_negative_turns, escalated, last_intent, last_sentiment, updated_at_utc, customer_name, account_type, unresolved_issues, campaign, journey, journey_state, clarification_count, retry_count, account_id, issue_summary)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(session_id) DO UPDATE SET
                  turns=excluded.turns,
                  consecutive_negative_turns=excluded.consecutive_negative_turns,
                  escalated=excluded.escalated,
                  last_intent=excluded.last_intent,
                  last_sentiment=excluded.last_sentiment,
                  updated_at_utc=excluded.updated_at_utc,
                  customer_name=excluded.customer_name,
                  account_type=excluded.account_type,
                  unresolved_issues=excluded.unresolved_issues,
                  campaign=excluded.campaign,
                  journey=excluded.journey,
                  journey_state=excluded.journey_state,
                  clarification_count=excluded.clarification_count,
                  retry_count=excluded.retry_count,
                  account_id=excluded.account_id,
                  issue_summary=excluded.issue_summary
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
            self.conn.commit()

    def get_session(self, session_id: UUID) -> SessionState | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM sessions WHERE session_id = ?", (str(session_id),)).fetchone()
        if row is None:
            return None
        return SessionState.from_db_row(row)

    def append_turn(self, *, session_id: UUID, request_id: str, user_text: str, bot_text: str, intent: str, sentiment: str, confidence: float) -> None:
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO turns(session_id, request_id, user_text, bot_text, intent, sentiment, confidence, created_at_utc)
                VALUES(?,?,?,?,?,?,?,?)
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
            self.conn.commit()

    def archive_turns_older_than(self, cutoff_iso: str) -> int:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM turns WHERE created_at_utc < ?", (cutoff_iso,)).fetchall()
            for row in rows:
                self.conn.execute(
                    """
                    INSERT INTO turns_archive(session_id, request_id, user_text, bot_text, intent, sentiment, confidence, created_at_utc, archived_at_utc)
                    VALUES(?,?,?,?,?,?,?,?,?)
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
            self.conn.execute("DELETE FROM turns WHERE created_at_utc < ?", (cutoff_iso,))
            self.conn.commit()
            return len(rows)
