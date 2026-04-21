from __future__ import annotations

from dataclasses import dataclass, field
import re

from .models import Intent, Sentiment, SessionState


@dataclass(frozen=True)
class PlanStep:
    action: str
    rationale: str
    priority: int


@dataclass
class BrainMemory:
    preferences: dict[str, str] = field(default_factory=dict)
    commitments: list[str] = field(default_factory=list)
    recent_facts: list[str] = field(default_factory=list)
    last_goal: str = ""


@dataclass(frozen=True)
class ReflectionResult:
    response_text: str
    concerns: tuple[str, ...] = ()


@dataclass(frozen=True)
class SafetyDecision:
    safe_text: str
    escalate: bool
    reason: str = "ok"


class Planner:
    def build_plan(
        self,
        *,
        state: SessionState,
        intent: Intent,
        sentiment: Sentiment,
        confident: bool,
        user_text: str,
    ) -> list[PlanStep]:
        plan: list[PlanStep] = []
        if not confident:
            plan.append(
                PlanStep(
                    action="clarify_request",
                    rationale="Low confidence requires clarification before commitment.",
                    priority=100,
                )
            )

        if intent in {Intent.support, Intent.refund} and not state.account_id:
            plan.append(
                PlanStep(
                    action="verify_account",
                    rationale="Sensitive support/refund operations require account verification.",
                    priority=90,
                )
            )

        if sentiment == Sentiment.negative:
            plan.append(
                PlanStep(
                    action="acknowledge_emotion",
                    rationale="Negative sentiment requires empathy before resolution steps.",
                    priority=80,
                )
            )

        if intent == Intent.sales:
            plan.append(
                PlanStep(
                    action="offer_eligible_product",
                    rationale="Provide compliant product fit plus campaign disclaimer.",
                    priority=70,
                )
            )

        if not plan:
            plan.append(PlanStep(action="resolve_directly", rationale="Intent and confidence are acceptable.", priority=50))
        return sorted(plan, key=lambda step: step.priority, reverse=True)


class MemoryManager:
    _PREFERENCE_PATTERNS = {
        "budget": re.compile(r"\b(cheap|budget|low cost|affordable)\b", re.IGNORECASE),
        "speed": re.compile(r"\b(speed|fast|latency)\b", re.IGNORECASE),
        "support_priority": re.compile(r"\b(urgent\w*|asap|immediately)\b", re.IGNORECASE),
    }

    def update_from_turn(self, memory: BrainMemory, state: SessionState, user_text: str, intent: Intent) -> None:
        memory.last_goal = intent.value

        lower = user_text.lower()
        for key, pattern in self._PREFERENCE_PATTERNS.items():
            if pattern.search(lower):
                memory.preferences[key] = "high"

        if state.customer_name:
            memory.recent_facts.append(f"customer_name:{state.customer_name}")

        trimmed = user_text.strip()
        if trimmed:
            memory.recent_facts.append(trimmed[:120])
            memory.recent_facts = memory.recent_facts[-6:]


class ReflectionLoop:
    def reflect(
        self,
        *,
        plan: list[PlanStep],
        response_text: str,
        confidence: float,
    ) -> ReflectionResult:
        concerns: list[str] = []
        revised = response_text

        if confidence < 0.45 and "?" not in revised:
            revised = f"{revised} Could you confirm the exact issue so I can help accurately?"
            concerns.append("added_clarifying_question")

        top_action = plan[0].action if plan else ""
        if top_action == "verify_account" and "account" not in revised.lower():
            revised = f"{revised} Please confirm your account ID to continue."
            concerns.append("added_account_verification")

        return ReflectionResult(response_text=revised, concerns=tuple(concerns))


class SafetyGovernor:
    _UNSAFE_PATTERNS = [
        re.compile(r"\b(ignore policy|bypass policy|guarantee forever)\b", re.IGNORECASE),
        re.compile(r"\b(send otp|share password|share pin)\b", re.IGNORECASE),
    ]

    def evaluate(self, response_text: str) -> SafetyDecision:
        for pattern in self._UNSAFE_PATTERNS:
            if pattern.search(response_text):
                return SafetyDecision(
                    safe_text="I can only assist using verified and secure steps. I am transferring you to a human specialist.",
                    escalate=True,
                    reason="unsafe_phrase_detected",
                )

        trimmed = response_text.strip()
        if len(trimmed) > 360:
            trimmed = f"{trimmed[:357]}..."
            return SafetyDecision(safe_text=trimmed, escalate=False, reason="length_trimmed")

        return SafetyDecision(safe_text=trimmed, escalate=False, reason="ok")
