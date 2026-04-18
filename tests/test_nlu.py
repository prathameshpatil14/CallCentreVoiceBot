import unittest

from callcentre_bot.nlu import InHouseNLUEngine


class _StubIntentModel:
    def __init__(self, predictions: dict[str, tuple[str, float]]) -> None:
        self._predictions = predictions

    def predict(self, text: str) -> tuple[str, float]:
        return self._predictions[text]


class NluCalibrationTests(unittest.TestCase):
    def test_calibration_counts_false_positives_from_other_intents(self) -> None:
        engine = InHouseNLUEngine.__new__(InHouseNLUEngine)
        engine.intent_model = _StubIntentModel(
            {
                "sales_hit": ("sales", 0.82),
                "sales_miss": ("support", 0.91),
                "support_fp_1": ("sales", 0.78),
                "support_fp_2": ("sales", 0.74),
                "support_fp_3": ("sales", 0.69),
            }
        )
        validation = [
            ("sales", "sales_hit"),
            ("sales", "sales_miss"),
            ("support", "support_fp_1"),
            ("support", "support_fp_2"),
            ("support", "support_fp_3"),
        ]

        thresholds = InHouseNLUEngine._calibrate_intent_thresholds(engine, validation)

        self.assertEqual(thresholds["sales"], 0.8)


if __name__ == "__main__":
    unittest.main()
