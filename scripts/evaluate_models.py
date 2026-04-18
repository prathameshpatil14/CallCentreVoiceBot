#!/usr/bin/env python3
import json
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from callcentre_bot.nlu import InHouseNLUEngine  # noqa: E402


def load_jsonl(path: Path) -> list[dict[str, str]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(label_type: str, records: list[dict[str, str]], predictor) -> None:
    labels = sorted({record["label"] for record in records})
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    correct = 0

    for record in records:
        expected = record["label"]
        predicted = predictor(record["text"])
        confusion[expected][predicted] += 1
        if expected == predicted:
            correct += 1

    accuracy = correct / max(1, len(records))
    print(f"[{label_type}] accuracy={accuracy:.3f}")

    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in labels if other != label)
        fn = sum(confusion[label][other] for other in labels if other != label)
        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        f1 = (2 * precision * recall) / max(1e-9, precision + recall)
        print(f"  {label:10s} precision={precision:.3f} recall={recall:.3f} f1={f1:.3f}")

    print("  confusion matrix:")
    for expected in labels:
        row = {pred: confusion[expected][pred] for pred in labels}
        print(f"    {expected}: {row}")


def main() -> None:
    nlu = InHouseNLUEngine()
    intent_records = load_jsonl(ROOT / "src/callcentre_bot/data/intent_test.jsonl")
    sentiment_records = load_jsonl(ROOT / "src/callcentre_bot/data/sentiment_test.jsonl")

    evaluate("intent", intent_records, lambda text: nlu.analyze(text).intent.value)
    evaluate("sentiment", sentiment_records, lambda text: nlu.analyze(text).sentiment.value)


if __name__ == "__main__":
    main()
