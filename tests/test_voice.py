import unittest
from unittest.mock import patch

from callcentre_bot.voice import (
    AudioChunk,
    LocalWhisperCppASRAdapter,
    OfflineASRAdapter,
    OfflineTTSAdapter,
    build_asr_adapter,
    build_tts_adapter,
)


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

    def test_local_whisper_raises_on_subprocess_failure(self) -> None:
        audio = AudioChunk(pcm16_bytes=b"\x00\x00" * 10, sample_rate_hz=16000)
        completed = unittest.mock.Mock(returncode=2, stderr="missing model", stdout="")
        with patch("callcentre_bot.voice.shutil.which", return_value="/usr/bin/whisper-cli"):
            adapter = LocalWhisperCppASRAdapter("whisper-cli")
        with patch("callcentre_bot.voice.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "whisper-cli failed"):
                adapter.transcribe(audio)


if __name__ == "__main__":
    unittest.main()
