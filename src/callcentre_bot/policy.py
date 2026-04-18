from dataclasses import dataclass

from .models import Intent, JourneyStateName, Sentiment


@dataclass(frozen=True)
class PolicyCandidate:
    text: str
    escalate: bool = False


class PolicyReranker:
    """Small in-house policy reranker over deterministic candidates."""

    def choose(
        self,
        *,
        candidates: list[PolicyCandidate],
        intent: Intent,
        sentiment: Sentiment,
        confidence: float,
        journey_state: JourneyStateName,
    ) -> PolicyCandidate:
        if not candidates:
            return PolicyCandidate(text="I will connect you with support.", escalate=True)

        best = candidates[0]
        best_score = -1e9
        for candidate in candidates:
            score = 0.0
            if candidate.escalate:
                score += 0.9 if sentiment == Sentiment.negative else -0.2
            if "refund" in candidate.text.lower() and intent == Intent.refund:
                score += 0.7
            if "upgrade" in candidate.text.lower() and intent == Intent.upsell:
                score += 0.6
            if journey_state == JourneyStateName.verify_account and "account" in candidate.text.lower():
                score += 0.8
            score += confidence * 0.3
            if score > best_score:
                best = candidate
                best_score = score
        return best
