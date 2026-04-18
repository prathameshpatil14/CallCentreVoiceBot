from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


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


class SessionCreateResponse(BaseModel):
    session_id: UUID = Field(default_factory=uuid4)


class UserTurnRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    channel: Literal["voice", "text"] = "voice"


class AssistantTurnResponse(BaseModel):
    text: str
    intent: Intent
    sentiment: Sentiment
    confidence: float = Field(ge=0.0, le=1.0)
    escalate_to_human: bool
    session_id: UUID
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionState(BaseModel):
    session_id: UUID
    turns: int = 0
    consecutive_negative_turns: int = 0
    escalated: bool = False
    last_intent: Intent = Intent.unknown
    last_sentiment: Sentiment = Sentiment.neutral
    updated_at_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
