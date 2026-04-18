from dataclasses import dataclass, field

from .dialog import BotReply, DialogPolicy
from .sentiment import detect_sentiment


@dataclass
class SessionState:
    turns: int = 0
    last_sentiment: str = "neutral"
    escalated: bool = False
    notes: list[str] = field(default_factory=list)


class VoiceSalesAssistant:
    def __init__(self) -> None:
        self.policy = DialogPolicy()
        self.state = SessionState()

    def handle_text(self, user_text: str) -> BotReply:
        sentiment = detect_sentiment(user_text)
        reply = self.policy.respond(user_text=user_text, sentiment=sentiment)

        self.state.turns += 1
        self.state.last_sentiment = sentiment
        self.state.escalated = reply.escalate_to_human
        self.state.notes.append(f"turn={self.state.turns}, sentiment={sentiment}")

        return reply
