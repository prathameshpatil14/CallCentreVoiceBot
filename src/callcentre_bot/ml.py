import math
import re
from collections import Counter, defaultdict


TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9']+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


class NaiveBayesTextClassifier:
    def __init__(self) -> None:
        self._class_doc_count: Counter[str] = Counter()
        self._token_count_by_class: dict[str, Counter[str]] = defaultdict(Counter)
        self._total_tokens_by_class: Counter[str] = Counter()
        self._vocabulary: set[str] = set()
        self._trained = False

    def train(self, examples: list[tuple[str, str]]) -> None:
        self._class_doc_count.clear()
        self._token_count_by_class.clear()
        self._total_tokens_by_class.clear()
        self._vocabulary.clear()

        for label, text in examples:
            self._class_doc_count[label] += 1
            tokens = tokenize(text)
            for token in tokens:
                self._token_count_by_class[label][token] += 1
                self._total_tokens_by_class[label] += 1
                self._vocabulary.add(token)

        self._trained = len(self._class_doc_count) > 0

    def predict(self, text: str) -> tuple[str, float]:
        if not self._trained:
            raise RuntimeError("Classifier not trained")

        tokens = tokenize(text)
        total_docs = sum(self._class_doc_count.values())
        vocab_size = max(1, len(self._vocabulary))

        best_label = None
        best_log_prob = -math.inf
        scores: dict[str, float] = {}

        for label, doc_count in self._class_doc_count.items():
            log_prob = math.log(doc_count / total_docs)
            label_total_tokens = self._total_tokens_by_class[label]
            denom = label_total_tokens + vocab_size

            for token in tokens:
                token_count = self._token_count_by_class[label][token]
                log_prob += math.log((token_count + 1) / denom)

            scores[label] = log_prob
            if log_prob > best_log_prob:
                best_label = label
                best_log_prob = log_prob

        if best_label is None:
            return "unknown", 0.0

        confidences = _softmax(scores)
        return best_label, confidences.get(best_label, 0.0)


def _softmax(log_probs: dict[str, float]) -> dict[str, float]:
    max_log_prob = max(log_probs.values())
    exps = {label: math.exp(value - max_log_prob) for label, value in log_probs.items()}
    total = sum(exps.values()) or 1.0
    return {label: value / total for label, value in exps.items()}
