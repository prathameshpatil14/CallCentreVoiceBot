import json
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib import request

from callcentre_bot.api import create_http_server
from callcentre_bot.config import settings


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

    def test_admin_drift_report_requires_api_key_when_configured(self) -> None:
        original_api_key = settings.api_key
        try:
            object.__setattr__(settings, "api_key", "secret-key")
            without_key = request.Request(
                "http://127.0.0.1:18080/v1/admin/drift-report",
                headers={"X-Role": "supervisor"},
            )
            with self.assertRaises(HTTPError) as raised:
                request.urlopen(without_key)
            self.assertEqual(raised.exception.code, 401)

            with_key = request.Request(
                "http://127.0.0.1:18080/v1/admin/drift-report",
                headers={"X-Role": "supervisor", "X-API-Key": "secret-key"},
            )
            with request.urlopen(with_key) as response:
                self.assertEqual(response.status, 200)
        finally:
            object.__setattr__(settings, "api_key", original_api_key)

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


if __name__ == "__main__":
    unittest.main()
