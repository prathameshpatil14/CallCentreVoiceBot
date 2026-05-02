from dataclasses import dataclass
from difflib import SequenceMatcher
from math import sqrt


@dataclass(frozen=True)
class Product:
    name: str
    price: str
    pitch: str


PRODUCTS = {
    "premium broadband": Product(
        name="Premium Broadband",
        price="$49/month",
        pitch="High-speed internet with unlimited data and 24/7 support.",
    ),
    "family mobile plan": Product(
        name="Family Mobile Plan",
        price="$79/month",
        pitch="Four lines with unlimited talk, text, and shared data.",
    ),
    "smart home security": Product(
        name="Smart Home Security",
        price="$29/month",
        pitch="24/7 monitoring, app alerts, and rapid emergency dispatch.",
    ),
}

FAQ = {
    "billing": "You can view bills in the app or request an email copy right now.",
    "refund": "Refunds are usually processed in 5-7 business days after approval.",
    "cancel": "You can cancel by verified phone request or from your account portal.",
    "support": "Technical support is available 24/7 on this line.",
    "upgrade": "I can compare your current plan and recommend an upgrade option now.",
    "insurance": "We can share policy benefits, coverage, exclusions, and premium options based on your needs.",
}


class KnowledgeRepository:
    def __init__(self) -> None:
        self._faq_vectors = {key: self._embed_text(key) for key in FAQ}
        self._product_vectors = {name: self._embed_text(name) for name in PRODUCTS}

    @staticmethod
    def _embed_text(text: str) -> dict[str, float]:
        vec: dict[str, float] = {}
        for token in text.lower().split():
            vec[token] = vec.get(token, 0.0) + 1.0
        norm = sqrt(sum(value * value for value in vec.values())) or 1.0
        return {token: value / norm for token, value in vec.items()}

    @staticmethod
    def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
        common = set(a) & set(b)
        return sum(a[token] * b[token] for token in common)

    @staticmethod
    def _match_score(text: str, key: str) -> float:
        base = SequenceMatcher(None, text, key).ratio()
        if key in text:
            return max(base, 0.95)
        return base

    def best_product_match(self, text: str) -> tuple[Product | None, float]:
        text_lower = text.lower().strip()
        text_vec = self._embed_text(text_lower)
        best_name = ""
        best_score = 0.0

        for name in PRODUCTS:
            score = self._match_score(text_lower, name)
            semantic = self._cosine_similarity(text_vec, self._product_vectors[name])
            score = max(score, semantic)
            if score > best_score:
                best_name = name
                best_score = score

        if not best_name:
            return None, 0.0
        return PRODUCTS[best_name], best_score

    def best_faq_match(self, text: str) -> tuple[str | None, float]:
        text_lower = text.lower().strip()
        text_vec = self._embed_text(text_lower)
        best_key = ""
        best_score = 0.0

        for key in FAQ:
            score = self._match_score(text_lower, key)
            semantic = self._cosine_similarity(text_vec, self._faq_vectors[key])
            score = max(score, semantic)
            if score > best_score:
                best_key = key
                best_score = score

        if not best_key:
            return None, 0.0
        return FAQ[best_key], best_score
