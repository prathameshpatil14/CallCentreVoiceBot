from dataclasses import dataclass
import importlib
import importlib.util
from pathlib import Path
from collections import Counter
import re

from .config import settings
from .json_codec import loads
from .ml import NaiveBayesTextClassifier
from .models import Intent, Sentiment


@dataclass
class NLUResult:
    intent: Intent
    sentiment: Sentiment
    confidence: float
    model_version: str
    intent_distribution: dict[str, float]
    language: str


NORMALIZATION_MAP = {
    "plz": "please",
    "u": "you",
    "yr": "your",
    "kaise": "how",
    "kya": "what",
    "nahi": "not",
    "chal": "working",
    "net": "internet",
    "मुझे": "mujhe",
    "चाहिए": "chahiye",
    "है": "hai",
    "नहीं": "nahi",
    "माझे": "maje",
    "मला": "mala",
    "पाहिजे": "pahije",
    "नको": "nako",
}

DEVANAGARI_PATTERN = re.compile(r"[\u0900-\u097F]")
HINGLISH_MARKERS = {"mujhe", "nahi", "kaise", "kya", "hai", "bill", "net"}
MARATHI_MARKERS = {"माझे", "मला", "पाहिजे", "नको", "कृपया", "योजना", "पैसे"}
_RAPIDFUZZ_SPEC = importlib.util.find_spec("rapidfuzz")
_RAPIDFUZZ_PROCESS = importlib.import_module("rapidfuzz.process") if _RAPIDFUZZ_SPEC else None
_NORMALIZATION_KEYS = tuple(NORMALIZATION_MAP.keys())


class InHouseNLUEngine:
    def __init__(self) -> None:
        self.intent_model = NaiveBayesTextClassifier()
        self.sentiment_model = NaiveBayesTextClassifier()
        self.model_version = f"nlu-{settings.model_variant}-2026.04"
        self.training_intent_distribution: dict[str, float] = {}
        self.calibrated_thresholds: dict[str, float] = {}
        self._train_models()

    def _normalize(self, text: str) -> str:
        words = re.findall(r"[\w\u0900-\u097F]+", text.lower())
        normalized = [self._normalize_token(word) for word in words]
        return " ".join(normalized)

    def _normalize_token(self, word: str) -> str:
        mapped = NORMALIZATION_MAP.get(word)
        if mapped is not None:
            return mapped
        if _RAPIDFUZZ_PROCESS is None:
            return word
        fuzzy_match = _RAPIDFUZZ_PROCESS.extractOne(word, _NORMALIZATION_KEYS, score_cutoff=90)
        if not fuzzy_match:
            return word
        return NORMALIZATION_MAP.get(fuzzy_match[0], word)

    def detect_language(self, text: str) -> str:
        lowered = text.lower()
        if DEVANAGARI_PATTERN.search(text):
            if any(marker in text for marker in MARATHI_MARKERS):
                return "mr"
            return "hi"
        if any(marker in lowered.split() for marker in HINGLISH_MARKERS):
            return "hinglish"
        return "en"

    def _load_examples(self, file_name: str) -> list[tuple[str, str]]:
        path = Path(__file__).parent / "data" / file_name
        examples: list[tuple[str, str]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = loads(line)
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
        intent_validation = self._load_split_examples("intent", "validation")
        sentiment_train = self._load_split_examples("sentiment", "train")
        self.intent_model.train(intent_train)
        self.sentiment_model.train(sentiment_train)
        self.training_intent_distribution = self._distribution([label for label, _ in intent_train])
        self.calibrated_thresholds = self._calibrate_intent_thresholds(intent_validation)

    def _calibrate_intent_thresholds(self, validation: list[tuple[str, str]]) -> dict[str, float]:
        if not validation:
            return {}
        by_intent: dict[str, list[tuple[str, float]]] = {}
        for expected_label, text in validation:
            predicted_label, confidence = self.intent_model.predict(text)
            by_intent.setdefault(expected_label, []).append((predicted_label, confidence))

        thresholds: dict[str, float] = {}
        for intent_label, rows in by_intent.items():
            best_threshold = 0.5
            best_f1 = -1.0
            for threshold in [x / 100 for x in range(35, 86, 5)]:
                tp = sum(1 for predicted, conf in rows if predicted == intent_label and conf >= threshold)
                fp = sum(1 for predicted, conf in rows if predicted != intent_label and conf >= threshold)
                fn = sum(1 for predicted, conf in rows if predicted == intent_label and conf < threshold)
                precision = tp / max(1, tp + fp)
                recall = tp / max(1, tp + fn)
                f1 = (2 * precision * recall) / max(1e-9, precision + recall)
                if f1 > best_f1:
                    best_f1 = f1
                    best_threshold = threshold
            thresholds[intent_label] = best_threshold
        return thresholds

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
        calibrated = self.calibrated_thresholds.get(intent.value)
        if calibrated is not None:
            return calibrated
        return thresholds.get(intent, settings.confidence_threshold)

    def _language_adjusted_threshold(self, intent: Intent, text: str) -> float:
        base = self._intent_threshold(intent)
        language = self.detect_language(text)
        adjustments = {
            "en": 0.0,
            "hinglish": -0.05,
            "hi": -0.07,
            "mr": -0.10,
        }
        floors = {
            "en": 0.35,
            "hinglish": 0.33,
            "hi": 0.32,
            "mr": 0.30,
        }
        floor = floors.get(language, 0.35)
        return max(floor, min(0.95, base + adjustments.get(language, 0.0)))

    def is_intent_confident(self, intent: Intent, confidence: float, text: str = "") -> bool:
        threshold = self._language_adjusted_threshold(intent, text) if text else self._intent_threshold(intent)
        return confidence >= threshold

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
        language = self.detect_language(text)
        return NLUResult(
            intent=intent,
            sentiment=sentiment,
            confidence=confidence,
            model_version=self.model_version,
            intent_distribution=self.training_intent_distribution,
            language=language,
        )
