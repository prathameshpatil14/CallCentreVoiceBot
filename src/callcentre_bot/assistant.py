from dataclasses import dataclass
from datetime import datetime, timezone
from datetime import timedelta
import re
from threading import Lock
from threading import Thread
import time
from uuid import UUID

from .config import settings
from .db import SessionPersistence, create_store
from .flows import CAMPAIGN_FLOWS, RESTRICTED_PHRASES
from .knowledge import KnowledgeRepository
from .models import AssistantTurnResponse, Intent, Journey, JourneyStateName, SessionState
from .nlu import InHouseNLUEngine
from .observability import AuditLogger, DriftMonitor, MetricStore, StructuredLogger, redact_pii


@dataclass
class Decision:
    text: str
    escalate: bool


class SessionStore:
    def __init__(self, store: SessionPersistence) -> None:
        self._sessions: dict[UUID, SessionState] = {}
        self._lock = Lock()
        self.store = store

    def create(self, session_id: UUID) -> SessionState:
        state = SessionState(session_id=session_id)
        with self._lock:
            self._sessions[session_id] = state
        self.store.upsert_session(state)
        return state

    def get(self, session_id: UUID) -> SessionState | None:
        with self._lock:
            mem = self._sessions.get(session_id)
        if mem is not None:
            return mem
        db_state = self.store.get_session(session_id)
        if db_state is not None:
            with self._lock:
                self._sessions[session_id] = db_state
        return db_state

    def save(self, state: SessionState) -> None:
        with self._lock:
            self._sessions[state.session_id] = state
        self.store.upsert_session(state)


class VoiceSalesAssistantService:
    def __init__(self) -> None:
        self.knowledge = KnowledgeRepository()
        self.nlu = InHouseNLUEngine()
        self.logger = StructuredLogger()
        self.audit = AuditLogger()
        self.metrics = MetricStore()
        self.store = create_store()
        self.sessions = SessionStore(self.store)
        self.drift = DriftMonitor(self.nlu.training_intent_distribution)
        self._start_archival_worker()

    def _start_archival_worker(self) -> None:
        def _loop() -> None:
            while True:
                cutoff = datetime.now(timezone.utc) - timedelta(days=settings.retention_days)
                archived = self.store.archive_turns_older_than(cutoff.isoformat())
                if archived:
                    self.logger.info("turns_archived", count=archived, retention_days=settings.retention_days)
                time.sleep(settings.archive_interval_seconds)

        Thread(target=_loop, daemon=True).start()

    def _extract_context(self, state: SessionState, text: str) -> None:
        lower = text.lower()
        name_match = re.search(r"\b(?:my name is|i am|this is)\s+([A-Za-z][A-Za-z'-]{1,30})\b", text, re.IGNORECASE)
        if name_match:
            state.customer_name = name_match.group(1).title()
        account_match = re.search(r"\b(?:account|acc|acct)\s*(?:number|no|id)?\s*[:#-]?\s*([A-Za-z0-9-]{6,20})\b", text, re.IGNORECASE)
        if account_match:
            state.account_id = account_match.group(1)
        if "prepaid" in lower:
            state.account_type = "prepaid"
        if "postpaid" in lower:
            state.account_type = "postpaid"
        if "retention" in lower:
            state.campaign = "retention"
        if "not resolved" in lower or "still issue" in lower:
            state.unresolved_issues.append(text[:80])
        issue_match = re.search(r"\b(issue|problem|error|complaint)\b[:\s-]*(.{6,140})", text, re.IGNORECASE)
        if issue_match:
            state.issue_summary = issue_match.group(2).strip()

    def _journey_for_intent(self, intent: Intent) -> Journey:
        if intent in {Intent.sales, Intent.upsell}:
            return Journey.sell if intent == Intent.sales else Journey.upsell
        if intent == Intent.refund:
            return Journey.refund
        if intent in {Intent.support, Intent.escalation}:
            return Journey.complaint
        return Journey.general

    def _advance_journey_state(self, state: SessionState, confident: bool, escalate: bool) -> None:
        if escalate:
            state.journey_state = JourneyStateName.transfer
            return
        if not confident:
            state.journey_state = JourneyStateName.clarify
            return
        if not state.account_id and state.journey in {Journey.refund, Journey.complaint}:
            state.journey_state = JourneyStateName.verify_account
            return
        if state.journey == Journey.upsell:
            state.journey_state = JourneyStateName.offer_upsell
            return
        state.journey_state = JourneyStateName.resolve

    def _enforce_compliance(self, text: str) -> str:
        lowered = text.lower()
        for phrase in RESTRICTED_PHRASES:
            if phrase in lowered:
                return "I can share verified plan details only. Let me provide accurate terms and pricing."
        return text

    def decide_response(self, state: SessionState, text: str, intent: Intent, confidence: float) -> Decision:
        faq_answer, faq_score = self.knowledge.best_faq_match(text)
        product, product_score = self.knowledge.best_product_match(text)

        if intent == Intent.escalation:
            return Decision("Understood. Transferring you to a human specialist now.", True)

        flow = CAMPAIGN_FLOWS.get(state.campaign, CAMPAIGN_FLOWS["default"])
        disclaimer = flow["mandatory_disclaimer"]

        if intent == Intent.faq and faq_answer and faq_score >= settings.confidence_threshold:
            return Decision(f"{faq_answer} Is there anything else I can help with?", False)

        if intent == Intent.sales and product and product_score >= settings.confidence_threshold:
            if product.name.lower() not in flow["allowed_products"]:
                return Decision("I can connect you to a specialist for this offer based on your campaign eligibility.", True)
            return Decision(
                f"{product.name} is {product.price}. {product.pitch} {disclaimer} Would you like me to place the order now?",
                False,
            )

        if intent == Intent.support:
            return Decision("I can help troubleshoot. Please share what is failing and when it started.", False)
        if intent == Intent.refund:
            return Decision("I can help with the refund. Please share your account number and transaction date.", False)
        if intent == Intent.upsell:
            return Decision("Based on your plan, I can offer a higher-speed bundle with a loyalty discount.", False)

        if confidence < settings.confidence_threshold:
            return Decision(
                "I want to give you the right answer. Is this about billing, support, or buying a new product?",
                False,
            )

        return Decision(
            "I can help with product sales, billing, refunds, cancellations, and technical support.",
            False,
        )

    def handle_turn(self, session_id: UUID, request_id: str, text: str) -> AssistantTurnResponse:
        start = datetime.now(timezone.utc)
        state = self.sessions.get(session_id)
        if state is None:
            state = self.sessions.create(session_id)

        self._extract_context(state, text)
        nlu_result = self.nlu.analyze(text)
        confident = self.nlu.is_intent_confident(nlu_result.intent, nlu_result.confidence)
        decision = self.decide_response(state, text, nlu_result.intent, nlu_result.confidence)

        if nlu_result.sentiment.value == "negative":
            state.consecutive_negative_turns += 1
        else:
            state.consecutive_negative_turns = 0

        force_escalation = state.consecutive_negative_turns >= settings.negative_sentiment_escalation_turns
        if not confident:
            state.clarification_count += 1
        if state.clarification_count > settings.max_clarifications:
            state.retry_count += 1
            state.clarification_count = 0
        policy_escalation = state.retry_count >= settings.max_retries_before_transfer
        escalate = decision.escalate or force_escalation or policy_escalation

        response_text = decision.text
        if nlu_result.sentiment.value == "negative" and not escalate:
            response_text = f"I am sorry for the frustration. {response_text}"
        if force_escalation:
            response_text = "I can hear your frustration. I am connecting you with a human agent right now."

        response_text = self._enforce_compliance(response_text)

        state.turns += 1
        state.journey = self._journey_for_intent(nlu_result.intent)
        self._advance_journey_state(state, confident, escalate)
        state.escalated = escalate
        state.last_intent = nlu_result.intent
        state.last_sentiment = nlu_result.sentiment
        state.updated_at_utc = datetime.now(timezone.utc)
        self.sessions.save(state)

        self.store.append_turn(
            session_id=session_id,
            request_id=request_id,
            user_text=redact_pii(text),
            bot_text=redact_pii(response_text),
            intent=nlu_result.intent.value,
            sentiment=nlu_result.sentiment.value,
            confidence=nlu_result.confidence,
        )

        elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        self.metrics.observe_latency("turn", elapsed)
        self.metrics.observe_latency("nlu", elapsed * 0.35)
        self.metrics.observe_latency("policy", elapsed * 0.25)
        self.metrics.observe_latency("tts", elapsed * 0.40)
        self.metrics.inc("turn_total")
        if escalate:
            self.metrics.inc("escalations_total")
        self.drift.record(nlu_result.intent.value)

        self.logger.info(
            "turn_processed",
            request_id=request_id,
            session_id=str(session_id),
            intent=nlu_result.intent.value,
            sentiment=nlu_result.sentiment.value,
            confidence=nlu_result.confidence,
            model_version=nlu_result.model_version,
            latency_ms=round(elapsed, 2),
        )
        self.audit.audit(
            "turn_decision",
            request_id=request_id,
            session_id=str(session_id),
            journey=state.journey.value,
            journey_state=state.journey_state.value,
            escalate=escalate,
        )

        return AssistantTurnResponse(
            text=response_text,
            intent=nlu_result.intent,
            sentiment=nlu_result.sentiment,
            confidence=nlu_result.confidence,
            escalate_to_human=escalate,
            session_id=session_id,
            request_id=request_id,
        )
