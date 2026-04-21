import unittest

from callcentre_bot.voice import OfflineASRAdapter, OfflineTTSAdapter, build_asr_adapter, build_tts_adapter


class VoiceAdapterTests(unittest.TestCase):
    def test_auto_mode_falls_back_when_engines_missing(self) -> None:
        asr = build_asr_adapter(mode="auto", whisper_command="missing-whisper-bin", fallback_enabled=True)
        tts = build_tts_adapter(
            mode="auto",
            piper_command="missing-piper-bin",
            piper_model_path="/tmp/missing-model.onnx",
            fallback_enabled=True,
        )
        self.assertIsInstance(asr, OfflineASRAdapter)
        self.assertIsInstance(tts, OfflineTTSAdapter)

    def test_production_mode_fails_fast_when_fallback_disabled(self) -> None:
        with self.assertRaises(RuntimeError):
            build_asr_adapter(mode="production", whisper_command="missing-whisper-bin", fallback_enabled=False)

        with self.assertRaises(RuntimeError):
            build_tts_adapter(
                mode="production",
                piper_command="missing-piper-bin",
                piper_model_path="/tmp/missing-model.onnx",
                fallback_enabled=False,
            )


if __name__ == "__main__":
    unittest.main()
