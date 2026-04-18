from dataclasses import dataclass
from typing import Optional


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
}


def find_product(query: str) -> Optional[Product]:
    query_lower = query.lower()
    for key, product in PRODUCTS.items():
        if key in query_lower:
            return product
    return None


def find_faq_answer(query: str) -> Optional[str]:
    query_lower = query.lower()
    for key, answer in FAQ.items():
        if key in query_lower:
            return answer
    return None
