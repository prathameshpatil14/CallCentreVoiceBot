import unittest

from callcentre_bot.models import Intent
from callcentre_bot.nlu import InHouseNLUEngine


class MultilingualNluTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.nlu = InHouseNLUEngine()

    def test_detect_language_hindi_marathi_hinglish(self) -> None:
        self.assertEqual(self.nlu.detect_language("मुझे नया प्लान चाहिए"), "hi")
        self.assertEqual(self.nlu.detect_language("मला नवीन प्लॅन पाहिजे"), "mr")
        self.assertEqual(self.nlu.detect_language("mujhe new plan chahiye"), "hinglish")

    def test_language_specific_thresholds_are_more_permissive_for_hi_mr(self) -> None:
        threshold_en = self.nlu._language_adjusted_threshold(Intent.sales, "I want to buy a plan")
        threshold_mr = self.nlu._language_adjusted_threshold(Intent.sales, "मला प्लॅन घ्यायचा आहे")
        self.assertLess(threshold_mr, threshold_en)


if __name__ == "__main__":
    unittest.main()
