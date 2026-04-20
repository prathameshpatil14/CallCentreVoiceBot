import json
import base64
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib import request

from callcentre_bot.api import create_http_server


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = create_http_server("127.0.0.1", 18080)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def test_health_and_metrics(self) -> None:
        with request.urlopen("http://127.0.0.1:18080/health") as response:
            self.assertEqual(response.status, 200)
            body = json.loads(response.read().decode("utf-8"))
            self.assertEqual(body["status"], "ok")

        with request.urlopen("http://127.0.0.1:18080/metrics") as response:
            self.assertEqual(response.status, 200)
            body = json.loads(response.read().decode("utf-8"))
            self.assertIn("request_id", body)

    def test_admin_drift_report_role_protection(self) -> None:
        req = request.Request("http://127.0.0.1:18080/v1/admin/drift-report")
        with self.assertRaises(HTTPError) as raised:
            request.urlopen(req)
        self.assertEqual(raised.exception.code, 403)

        privileged = request.Request(
            "http://127.0.0.1:18080/v1/admin/drift-report",
            headers={"X-Role": "supervisor"},
        )
        with request.urlopen(privileged) as response:
            self.assertEqual(response.status, 200)
            body = json.loads(response.read().decode("utf-8"))
            self.assertIn("status", body)

    def test_sales_flow(self) -> None:
        create_req = request.Request("http://127.0.0.1:18080/v1/sessions", method="POST")
        with request.urlopen(create_req) as create_resp:
            payload = json.loads(create_resp.read().decode("utf-8"))
            session_id = payload["session_id"]
            self.assertIn("request_id", payload)

        body = json.dumps({"text": "I want to buy family mobile plan"}).encode("utf-8")
        turn_req = request.Request(
            f"http://127.0.0.1:18080/v1/sessions/{session_id}/turns",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(turn_req) as turn_resp:
            reply = json.loads(turn_resp.read().decode("utf-8"))
            self.assertEqual(reply["intent"], "sales")
            self.assertIn("Family Mobile Plan", reply["text"])
            self.assertIn("request_id", reply)

    def test_negative_escalation_threshold(self) -> None:
        create_req = request.Request("http://127.0.0.1:18080/v1/sessions", method="POST")
        with request.urlopen(create_req) as create_resp:
            session_id = json.loads(create_resp.read().decode("utf-8"))["session_id"]

        payload = json.dumps({"text": "I am upset and this is terrible"}).encode("utf-8")
        url = f"http://127.0.0.1:18080/v1/sessions/{session_id}/turns"

        def call_turn() -> dict:
            turn_req = request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(turn_req) as turn_resp:
                return json.loads(turn_resp.read().decode("utf-8"))

        first = call_turn()
        second = call_turn()
        third = call_turn()

        self.assertFalse(first["escalate_to_human"])
        self.assertFalse(second["escalate_to_human"])
        self.assertTrue(third["escalate_to_human"])

    def test_name_extraction_handles_missing_name_token(self) -> None:
        create_req = request.Request("http://127.0.0.1:18080/v1/sessions", method="POST")
        with request.urlopen(create_req) as create_resp:
            session_id = json.loads(create_resp.read().decode("utf-8"))["session_id"]

        body = json.dumps({"text": "my name is   "}).encode("utf-8")
        turn_req = request.Request(
            f"http://127.0.0.1:18080/v1/sessions/{session_id}/turns",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(turn_req) as turn_resp:
            reply = json.loads(turn_resp.read().decode("utf-8"))

        self.assertIn("text", reply)
        self.assertIn("request_id", reply)

    def test_human_like_consciousness_personalizes_response(self) -> None:
        create_req = request.Request("http://127.0.0.1:18080/v1/sessions", method="POST")
        with request.urlopen(create_req) as create_resp:
            session_id = json.loads(create_resp.read().decode("utf-8"))["session_id"]

        intro_payload = json.dumps({"text": "my name is rita"}).encode("utf-8")
        intro_req = request.Request(
            f"http://127.0.0.1:18080/v1/sessions/{session_id}/turns",
            data=intro_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(intro_req) as intro_resp:
            self.assertEqual(intro_resp.status, 200)

        follow_payload = json.dumps({"text": "I need help with billing support"}).encode("utf-8")
        follow_req = request.Request(
            f"http://127.0.0.1:18080/v1/sessions/{session_id}/turns",
            data=follow_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(follow_req) as follow_resp:
            reply = json.loads(follow_resp.read().decode("utf-8"))

        self.assertIn("Rita", reply["text"])

    def test_voice_turn_endpoint_returns_audio_and_transcript(self) -> None:
        create_req = request.Request("http://127.0.0.1:18080/v1/sessions", method="POST")
        with request.urlopen(create_req) as create_resp:
            session_id = json.loads(create_resp.read().decode("utf-8"))["session_id"]

        fake_audio = base64.b64encode(b"I need billing support").decode("ascii")
        body = json.dumps({"audio_base64": fake_audio, "sample_rate_hz": 16000}).encode("utf-8")
        voice_req = request.Request(
            f"http://127.0.0.1:18080/v1/sessions/{session_id}/voice-turns",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with request.urlopen(voice_req) as voice_resp:
            payload = json.loads(voice_resp.read().decode("utf-8"))

        self.assertEqual(voice_resp.status, 200)
        self.assertIn("transcript", payload)
        self.assertIn("audio_base64", payload)
        self.assertTrue(len(payload["audio_base64"]) > 0)

    def test_voice_turn_rejects_invalid_audio(self) -> None:
        create_req = request.Request("http://127.0.0.1:18080/v1/sessions", method="POST")
        with request.urlopen(create_req) as create_resp:
            session_id = json.loads(create_resp.read().decode("utf-8"))["session_id"]

        body = json.dumps({"audio_base64": "not-valid-base64"}).encode("utf-8")
        voice_req = request.Request(
            f"http://127.0.0.1:18080/v1/sessions/{session_id}/voice-turns",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as raised:
            request.urlopen(voice_req)
        self.assertEqual(raised.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
