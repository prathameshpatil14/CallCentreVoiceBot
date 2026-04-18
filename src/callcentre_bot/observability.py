import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock


PII_PATTERNS = [
    re.compile(r"\b\d{10}\b"),
    re.compile(r"\b[\w.%-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:acc|account)\s*[:#-]?\s*\d{4,}\b", re.IGNORECASE),
]


def redact_pii(text: str) -> str:
    redacted = text
    for pattern in PII_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


class StructuredLogger:
    def info(self, event: str, **kwargs: object) -> None:
        payload = {"event": event, "ts": time.time(), **kwargs}
        print(json.dumps(payload, ensure_ascii=False))


@dataclass
class MetricStore:
    counters: dict[str, int]
    latency_totals_ms: dict[str, float]

    def __init__(self) -> None:
        self.counters = defaultdict(int)
        self.latency_totals_ms = defaultdict(float)
        self._lock = Lock()

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            self.counters[name] += value

    def observe_latency(self, name: str, latency_ms: float) -> None:
        with self._lock:
            self.counters[f"{name}_count"] += 1
            self.latency_totals_ms[name] += latency_ms

    def snapshot(self) -> dict[str, float | int]:
        with self._lock:
            data: dict[str, float | int] = dict(self.counters)
            for name, total in self.latency_totals_ms.items():
                count = self.counters.get(f"{name}_count", 1)
                data[f"{name}_avg_ms"] = total / max(1, count)
            return data
