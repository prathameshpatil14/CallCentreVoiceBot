from dataclasses import dataclass
import json
from pathlib import Path

from .config import settings
from .ml import NaiveBayesTextClassifier
from .models import Intent, Sentiment


@dataclass
class NLUResult:
    intent: Intent
    sentiment: Sentiment
    confidence: float
    model_version: str


NORMALIZATION_MAP = {
    "plz": "please",
    "u": "you",
    "yr": "your",
    "kaise": "how",
    "kya": "what",
    "nahi": "not",
    "chal": "working",
    "net": "internet",
}


class InHouseNLUEngine:
    def __init__(self) -> None:
        self.intent_model = NaiveBayesTextClassifier()
        self.sentiment_model = NaiveBayesTextClassifier()
        self.model_version = f"nlu-{settings.model_variant}-2026.04"
        self._train_models()

    def _normalize(self, text: str) -> str:
        words = text.lower().split()
        normalized = [NORMALIZATION_MAP.get(word, word) for word in words]
        return " ".join(normalized)

    def _load_examples(self, file_name: str) -> list[tuple[str, str]]:
        path = Path(__file__).parent / "data" / file_name
        examples: list[tuple[str, str]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            label = str(payload["label"])
            text = self._normalize(str(payload["text"]))
            if settings.model_variant == "B":
                text = f"{text} customer"
            examples.append((label, text))
        return examples

    def _train_models(self) -> None:
        intent_examples = self._load_examples("intent_samples.jsonl")
        sentiment_examples = self._load_examples("sentiment_samples.jsonl")
        self.intent_model.train(intent_examples)
        self.sentiment_model.train(sentiment_examples)

    def analyze(self, text: str) -> NLUResult:
        normalized = self._normalize(text)
        intent_label, intent_conf = self.intent_model.predict(normalized)
        sentiment_label, sentiment_conf = self.sentiment_model.predict(normalized)

        try:
            intent = Intent(intent_label)
        except ValueError:
            intent = Intent.unknown

        try:
            sentiment = Sentiment(sentiment_label)
        except ValueError:
            sentiment = Sentiment.neutral

        confidence = (intent_conf + sentiment_conf) / 2
        return NLUResult(intent=intent, sentiment=sentiment, confidence=confidence, model_version=self.model_version)
