from dataclasses import dataclass

from .models import Intent, Sentiment


@dataclass
class NLUResult:
    intent: Intent
    sentiment: Sentiment
    confidence: float


class RuleBasedNLUEngine:
    NEGATIVE_WORDS = {
        "angry",
        "bad",
        "frustrated",
        "issue",
        "not working",
        "terrible",
        "upset",
    }

    POSITIVE_WORDS = {"awesome", "good", "great", "happy", "love", "perfect", "thanks"}

    SALES_WORDS = {"buy", "purchase", "plan", "price", "offer", "deal"}
    FAQ_WORDS = {"billing", "refund", "cancel", "support", "upgrade"}
    ESCALATE_WORDS = {"agent", "human", "representative", "manager", "complaint"}

    def analyze(self, text: str) -> NLUResult:
        text_lower = text.lower().strip()

        sentiment = Sentiment.neutral
        if any(token in text_lower for token in self.NEGATIVE_WORDS):
            sentiment = Sentiment.negative
        elif any(token in text_lower for token in self.POSITIVE_WORDS):
            sentiment = Sentiment.positive

        if any(token in text_lower for token in self.ESCALATE_WORDS):
            return NLUResult(Intent.escalation, sentiment, 0.92)

        if any(token in text_lower for token in self.FAQ_WORDS):
            return NLUResult(Intent.faq, sentiment, 0.80)

        if any(token in text_lower for token in self.SALES_WORDS):
            return NLUResult(Intent.sales, sentiment, 0.78)

        if "help" in text_lower or "problem" in text_lower:
            return NLUResult(Intent.support, sentiment, 0.70)

        return NLUResult(Intent.unknown, sentiment, 0.50)
