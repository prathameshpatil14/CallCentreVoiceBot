import json
import http.client
import threading
import time
import unittest
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

    def test_health(self) -> None:
        with request.urlopen("http://127.0.0.1:18080/health") as response:
            self.assertEqual(response.status, 200)
            body = json.loads(response.read().decode("utf-8"))
            self.assertEqual(body["status"], "ok")

    def test_sales_flow(self) -> None:
        create_req = request.Request("http://127.0.0.1:18080/v1/sessions", method="POST")
        with request.urlopen(create_req) as create_resp:
            session_id = json.loads(create_resp.read().decode("utf-8"))["session_id"]

        payload = json.dumps({"text": "I want to buy family mobile plan"}).encode("utf-8")
        turn_req = request.Request(
            f"http://127.0.0.1:18080/v1/sessions/{session_id}/turns",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(turn_req) as turn_resp:
            body = json.loads(turn_resp.read().decode("utf-8"))
            self.assertEqual(body["intent"], "sales")
            self.assertIn("Family Mobile Plan", body["text"])

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

    def test_invalid_content_length_returns_bad_request(self) -> None:
        create_req = request.Request("http://127.0.0.1:18080/v1/sessions", method="POST")
        with request.urlopen(create_req) as create_resp:
            session_id = json.loads(create_resp.read().decode("utf-8"))["session_id"]

        conn = http.client.HTTPConnection("127.0.0.1", 18080)
        conn.request(
            "POST",
            f"/v1/sessions/{session_id}/turns",
            body="{}",
            headers={"Content-Type": "application/json", "Content-Length": "abc"},
        )
        response = conn.getresponse()
        body = json.loads(response.read().decode("utf-8"))
        conn.close()

        self.assertEqual(response.status, 400)
        self.assertEqual(body["error"], "invalid content-length")


if __name__ == "__main__":
    unittest.main()
