from pathlib import Path
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from threading import Lock

from .json_codec import dumps


PII_PATTERNS = [
    re.compile(r"\b\d{10}\b"),
    re.compile(r"\b[\w.%-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:acc|account)\s*[:#-]?\s*\d{4,}\b", re.IGNORECASE),
    re.compile(r"\b[a-z]{5}\d{4}[a-z]\b", re.IGNORECASE),  # PAN
    re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),  # Aadhaar
    re.compile(r"\b(?:कार्ड|खाता|account|acct|iban|ifsc)\s*[:#-]?\s*[A-Za-z0-9-]{4,}\b", re.IGNORECASE),
]


def redact_pii(text: str) -> str:
    redacted = text
    for pattern in PII_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


class StructuredLogger:
    def info(self, event: str, **kwargs: object) -> None:
        payload = {"event": event, "ts": time.time(), **kwargs}
        print(dumps(payload))


class AuditLogger(StructuredLogger):
    def audit(self, action: str, **kwargs: object) -> None:
        self.info("audit", action=action, **kwargs)


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


class DriftMonitor:
    def __init__(self, baseline_distribution: dict[str, float]) -> None:
        self.baseline = baseline_distribution
        self.production_counts: Counter[str] = Counter()
        self._lock = Lock()

    def record(self, intent_label: str) -> None:
        with self._lock:
            self.production_counts[intent_label] += 1

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            total = sum(self.production_counts.values()) or 1
            current = {label: count / total for label, count in self.production_counts.items()}
        labels = set(self.baseline) | set(current)
        drift = {
            f"drift_{label}": abs(self.baseline.get(label, 0.0) - current.get(label, 0.0))
            for label in labels
        }
        drift["drift_max"] = max(drift.values()) if drift else 0.0
        return drift

    def persist_weekly_snapshot(self, output_path: str) -> dict[str, float]:
        payload = {"ts": time.time(), "drift": self.snapshot()}
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(dumps(payload) + "\n")
        return payload["drift"]
