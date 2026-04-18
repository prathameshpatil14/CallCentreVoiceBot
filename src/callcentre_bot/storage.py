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
                    campaign TEXT
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
            self.conn.commit()

    def upsert_session(self, state: SessionState) -> None:
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO sessions(session_id, turns, consecutive_negative_turns, escalated, last_intent, last_sentiment, updated_at_utc, customer_name, account_type, unresolved_issues, campaign)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
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
                  campaign=excluded.campaign
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
