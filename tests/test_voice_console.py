import base64
import json
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_voice_console.py"
SPEC = importlib.util.spec_from_file_location("run_voice_console", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
command_exists = MODULE.command_exists
send_voice_turn = MODULE.send_voice_turn


class VoiceConsoleTests(unittest.TestCase):
    def test_command_exists_uses_shutil_which(self) -> None:
        with patch.object(MODULE.shutil, "which", return_value="/usr/bin/arecord"):
            self.assertTrue(command_exists("arecord"))

        with patch.object(MODULE.shutil, "which", return_value=None):
            self.assertFalse(command_exists("arecord"))

    def test_send_voice_turn_posts_base64_audio(self) -> None:
        fake_response = Mock()
        fake_response.read.return_value = json.dumps({"text": "ok", "audio_base64": ""}).encode("utf-8")
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = lambda s, exc_type, exc, tb: False

        with patch.object(MODULE.request, "urlopen", return_value=fake_response) as mocked_urlopen:
            reply = send_voice_turn(
                base_url="http://127.0.0.1:8080",
                session_id="abc",
                audio_bytes=b"hello",
                sample_rate_hz=16000,
            )

        self.assertEqual(reply["text"], "ok")
        req = mocked_urlopen.call_args.args[0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(base64.b64decode(body["audio_base64"]), b"hello")
        self.assertEqual(body["sample_rate_hz"], 16000)


if __name__ == "__main__":
    unittest.main()
