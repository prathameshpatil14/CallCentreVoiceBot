from typing import Literal

Sentiment = Literal["positive", "neutral", "negative"]


NEGATIVE_WORDS = {
    "angry",
    "bad",
    "cancel",
    "complaint",
    "frustrated",
    "hate",
    "issue",
    "not working",
    "terrible",
    "upset",
}

POSITIVE_WORDS = {
    "awesome",
    "good",
    "great",
    "happy",
    "love",
    "perfect",
    "thanks",
}


def detect_sentiment(text: str) -> Sentiment:
    lower = text.lower()
    if any(token in lower for token in NEGATIVE_WORDS):
        return "negative"
    if any(token in lower for token in POSITIVE_WORDS):
        return "positive"
    return "neutral"
