from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Callable, TypeVar
from uuid import UUID

from .config import settings
from .knowledge import KnowledgeRepository
from .models import AssistantTurnResponse, Intent, SessionState
from .nlu import InHouseNLUEngine


@dataclass
class Decision:
    text: str
    escalate: bool


T = TypeVar("T")


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

    def mutate(self, session_id: UUID, mutator: Callable[[SessionState], T]) -> T:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                state = SessionState(session_id=session_id)
                self._sessions[session_id] = state
            result = mutator(state)
            self._sessions[session_id] = state
            return result


class VoiceSalesAssistantService:
    def __init__(self) -> None:
        self.knowledge = KnowledgeRepository()
        self.nlu = InHouseNLUEngine()
        self.sessions = SessionStore()

    def decide_response(self, text: str, intent: Intent, confidence: float) -> Decision:
        faq_answer, faq_score = self.knowledge.best_faq_match(text)
        product, product_score = self.knowledge.best_product_match(text)

        if intent == Intent.escalation:
            return Decision("Understood. Transferring you to a human specialist now.", True)

        if intent == Intent.faq and faq_answer and faq_score >= settings.confidence_threshold:
            return Decision(f"{faq_answer} Is there anything else I can help with?", False)

        if intent == Intent.sales and product and product_score >= settings.confidence_threshold:
            return Decision(
                f"{product.name} is {product.price}. {product.pitch} Would you like me to place the order now?",
                False,
            )

        if intent == Intent.support:
            return Decision("I can help troubleshoot. Please share what is failing and when it started.", False)

        if confidence < settings.confidence_threshold:
            return Decision(
                "I want to give you the right answer. Is this about billing, support, or buying a new product?",
                False,
            )

        return Decision(
            "I can help with product sales, billing, refunds, cancellations, and technical support.",
            False,
        )

    def handle_turn(self, session_id: UUID, text: str) -> AssistantTurnResponse:
        nlu_result = self.nlu.analyze(text)
        decision = self.decide_response(text, nlu_result.intent, nlu_result.confidence)
        now = datetime.now(timezone.utc)

        def _update_state(state: SessionState) -> tuple[bool, str]:
            if nlu_result.sentiment.value == "negative":
                state.consecutive_negative_turns += 1
            else:
                state.consecutive_negative_turns = 0

            force_escalation = state.consecutive_negative_turns >= settings.negative_sentiment_escalation_turns
            escalate = decision.escalate or force_escalation

            response_text = decision.text
            if nlu_result.sentiment.value == "negative" and not escalate:
                response_text = f"I am sorry for the frustration. {response_text}"
            if force_escalation:
                response_text = "I can hear your frustration. I am connecting you with a human agent right now."

            state.turns += 1
            state.escalated = escalate
            state.last_intent = nlu_result.intent
            state.last_sentiment = nlu_result.sentiment
            state.updated_at_utc = now
            return escalate, response_text

        escalate, response_text = self.sessions.mutate(session_id, _update_state)

        return AssistantTurnResponse(
            text=response_text,
            intent=nlu_result.intent,
            sentiment=nlu_result.sentiment,
            confidence=nlu_result.confidence,
            escalate_to_human=escalate,
            session_id=session_id,
        )
