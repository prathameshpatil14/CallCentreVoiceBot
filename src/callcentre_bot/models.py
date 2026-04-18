from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class Sentiment(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class Intent(str, Enum):
    sales = "sales"
    faq = "faq"
    support = "support"
    escalation = "escalation"
    unknown = "unknown"


@dataclass
class SessionCreateResponse:
    session_id: UUID = field(default_factory=uuid4)

    def to_dict(self) -> dict[str, Any]:
        return {"session_id": str(self.session_id)}


@dataclass
class UserTurnRequest:
    text: str
    channel: str = "voice"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "UserTurnRequest":
        text = str(payload.get("text", "")).strip()
        channel = str(payload.get("channel", "voice"))
        return cls(text=text, channel=channel)


@dataclass
class AssistantTurnResponse:
    text: str
    intent: Intent
    sentiment: Sentiment
    confidence: float
    escalate_to_human: bool
    session_id: UUID
    request_id: str
    timestamp_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["intent"] = self.intent.value
        data["sentiment"] = self.sentiment.value
        data["session_id"] = str(self.session_id)
        data["timestamp_utc"] = self.timestamp_utc.isoformat()
        return data


@dataclass
class SessionState:
    session_id: UUID
    turns: int = 0
    consecutive_negative_turns: int = 0
    escalated: bool = False
    last_intent: Intent = Intent.unknown
    last_sentiment: Sentiment = Sentiment.neutral
    customer_name: str = ""
    account_type: str = ""
    unresolved_issues: list[str] = field(default_factory=list)
    campaign: str = "default"
    updated_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": str(self.session_id),
            "turns": self.turns,
            "consecutive_negative_turns": self.consecutive_negative_turns,
            "escalated": self.escalated,
            "last_intent": self.last_intent.value,
            "last_sentiment": self.last_sentiment.value,
            "customer_name": self.customer_name,
            "account_type": self.account_type,
            "unresolved_issues": self.unresolved_issues,
            "campaign": self.campaign,
            "updated_at_utc": self.updated_at_utc.isoformat(),
        }

    @classmethod
    def from_db_row(cls, row: Any) -> "SessionState":
        return cls(
            session_id=UUID(row["session_id"]),
            turns=int(row["turns"]),
            consecutive_negative_turns=int(row["consecutive_negative_turns"]),
            escalated=bool(row["escalated"]),
            last_intent=Intent(str(row["last_intent"])),
            last_sentiment=Sentiment(str(row["last_sentiment"])),
            customer_name=str(row["customer_name"] or ""),
            account_type=str(row["account_type"] or ""),
            unresolved_issues=(str(row["unresolved_issues"] or "").split("|") if row["unresolved_issues"] else []),
            campaign=str(row["campaign"] or "default"),
            updated_at_utc=datetime.fromisoformat(str(row["updated_at_utc"])),
        )
