from dataclasses import dataclass

from .ml import NaiveBayesTextClassifier
from .models import Intent, Sentiment


@dataclass
class NLUResult:
    intent: Intent
    sentiment: Sentiment
    confidence: float


class InHouseNLUEngine:
    def __init__(self) -> None:
        self.intent_model = NaiveBayesTextClassifier()
        self.sentiment_model = NaiveBayesTextClassifier()
        self._train_models()

    def _train_models(self) -> None:
        intent_examples: list[tuple[str, str]] = [
            ("sales", "I want to buy a new internet plan"),
            ("sales", "Show me your best deal and price"),
            ("sales", "I am interested in family mobile plan"),
            ("faq", "How do I check billing details"),
            ("faq", "How long does refund processing take"),
            ("faq", "Can I cancel my account"),
            ("support", "My service is not working"),
            ("support", "Internet problem started yesterday"),
            ("support", "Need technical support for device"),
            ("escalation", "Connect me to human agent"),
            ("escalation", "I need your manager now"),
            ("escalation", "Transfer this complaint to representative"),
            ("unknown", "hello there"),
            ("unknown", "good morning"),
        ]
        sentiment_examples: list[tuple[str, str]] = [
            ("positive", "thanks great support awesome"),
            ("positive", "perfect this is good"),
            ("positive", "love this plan happy customer"),
            ("negative", "I am upset this is terrible"),
            ("negative", "bad service angry and frustrated"),
            ("negative", "hate this issue not working"),
            ("neutral", "what is the monthly price"),
            ("neutral", "please explain refund process"),
            ("neutral", "I need information about support"),
        ]

        self.intent_model.train(intent_examples)
        self.sentiment_model.train(sentiment_examples)

    def analyze(self, text: str) -> NLUResult:
        intent_label, intent_conf = self.intent_model.predict(text)
        sentiment_label, sentiment_conf = self.sentiment_model.predict(text)

        try:
            intent = Intent(intent_label)
        except ValueError:
            intent = Intent.unknown

        try:
            sentiment = Sentiment(sentiment_label)
        except ValueError:
            sentiment = Sentiment.neutral

        confidence = (intent_conf + sentiment_conf) / 2
        return NLUResult(intent=intent, sentiment=sentiment, confidence=confidence)
