from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from uuid import UUID

from .config import settings
from .knowledge import KnowledgeRepository
from .models import AssistantTurnResponse, Intent, SessionState
from .nlu import RuleBasedNLUEngine


@dataclass
class Decision:
    text: str
    escalate: bool


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[UUID, SessionState] = {}
        self._lock = Lock()

    def create(self, session_id: UUID) -> SessionState:
        state = SessionState(session_id=session_id)
        with self._lock:
            self._sessions[session_id] = state
        return state

    def get(self, session_id: UUID) -> SessionState | None:
        with self._lock:
            return self._sessions.get(session_id)

    def save(self, state: SessionState) -> None:
        with self._lock:
            self._sessions[state.session_id] = state


class VoiceSalesAssistantService:
    def __init__(self) -> None:
        self.knowledge = KnowledgeRepository()
        self.nlu = RuleBasedNLUEngine()
        self.sessions = SessionStore()

    def decide_response(self, text: str, intent: Intent, confidence: float) -> Decision:
        faq_answer, faq_score = self.knowledge.best_faq_match(text)
        product, product_score = self.knowledge.best_product_match(text)

        if intent == Intent.escalation:
            return Decision(
                text="I understand. I am transferring you to a human specialist now.",
                escalate=True,
            )

        if intent == Intent.faq and faq_answer and faq_score >= settings.confidence_threshold:
            return Decision(text=f"{faq_answer} Would you like anything else?", escalate=False)

        if intent == Intent.sales and product and product_score >= settings.confidence_threshold:
            return Decision(
                text=(
                    f"{product.name} is {product.price}. {product.pitch} "
                    "I can place the order now if you would like."
                ),
                escalate=False,
            )

        if intent == Intent.support:
            return Decision(
                text="I can help troubleshoot. Please describe the issue and when it started.",
                escalate=False,
            )

        if confidence < settings.confidence_threshold:
            return Decision(
                text="I want to give you the right answer. Could you share whether this is billing, support, or a new purchase?",
                escalate=False,
            )

        return Decision(
            text="I can help with plans, billing, refunds, and technical support. How can I help today?",
            escalate=False,
        )

    def handle_turn(self, session_id: UUID, text: str) -> AssistantTurnResponse:
        state = self.sessions.get(session_id)
        if state is None:
            state = self.sessions.create(session_id)

        nlu_result = self.nlu.analyze(text)
        decision = self.decide_response(text, nlu_result.intent, nlu_result.confidence)

        if nlu_result.sentiment.value == "negative":
            state.consecutive_negative_turns += 1
        else:
            state.consecutive_negative_turns = 0

        forced_escalation = state.consecutive_negative_turns >= settings.negative_sentiment_escalation_turns
        escalate = decision.escalate or forced_escalation

        response_text = decision.text
        if nlu_result.sentiment.value == "negative" and not escalate:
            response_text = f"I am sorry for the frustration. {response_text}"
        if forced_escalation:
            response_text = "I can hear your frustration. I am connecting you with a human agent now."

        state.turns += 1
        state.escalated = escalate
        state.last_intent = nlu_result.intent
        state.last_sentiment = nlu_result.sentiment
        state.updated_at_utc = datetime.now(timezone.utc)
        self.sessions.save(state)

        return AssistantTurnResponse(
            text=response_text,
            intent=nlu_result.intent,
            sentiment=nlu_result.sentiment,
            confidence=nlu_result.confidence,
            escalate_to_human=escalate,
            session_id=session_id,
        )
