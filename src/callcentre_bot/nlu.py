from dataclasses import dataclass
import json
from pathlib import Path
from collections import Counter

from .config import settings
from .ml import NaiveBayesTextClassifier
from .models import Intent, Sentiment


@dataclass
class NLUResult:
    intent: Intent
    sentiment: Sentiment
    confidence: float
    model_version: str
    intent_distribution: dict[str, float]


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
        self.training_intent_distribution: dict[str, float] = {}
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

    def _load_split_examples(self, prefix: str, split: str) -> list[tuple[str, str]]:
        split_file = Path(__file__).parent / "data" / f"{prefix}_{split}.jsonl"
        if split_file.exists():
            return self._load_examples(split_file.name)
        fallback = Path(__file__).parent / "data" / f"{prefix}_samples.jsonl"
        if fallback.exists():
            return self._load_examples(fallback.name)
        return []

    def _train_models(self) -> None:
        intent_train = self._load_split_examples("intent", "train")
        sentiment_train = self._load_split_examples("sentiment", "train")
        self.intent_model.train(intent_train)
        self.sentiment_model.train(sentiment_train)
        self.training_intent_distribution = self._distribution([label for label, _ in intent_train])

    def _distribution(self, labels: list[str]) -> dict[str, float]:
        total = len(labels) or 1
        counts = Counter(labels)
        return {label: count / total for label, count in counts.items()}

    def _intent_threshold(self, intent: Intent) -> float:
        thresholds = {
            Intent.sales: settings.intent_threshold_sales,
            Intent.support: settings.intent_threshold_support,
            Intent.escalation: settings.intent_threshold_escalation,
            Intent.refund: settings.intent_threshold_refund,
            Intent.upsell: settings.intent_threshold_upsell,
        }
        return thresholds.get(intent, settings.confidence_threshold)

    def is_intent_confident(self, intent: Intent, confidence: float) -> bool:
        return confidence >= self._intent_threshold(intent)

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
        return NLUResult(
            intent=intent,
            sentiment=sentiment,
            confidence=confidence,
            model_version=self.model_version,
            intent_distribution=self.training_intent_distribution,
        )
