import json
import os
import threading
import time
import unittest
from urllib import request
from urllib.error import HTTPError

from callcentre_bot.api import BotRequestHandler, create_http_server
from callcentre_bot.config import settings


class ChaosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = create_http_server("127.0.0.1", 18081)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def test_internal_failure_returns_500(self) -> None:
        original = BotRequestHandler.service.handle_turn

        def boom(*args, **kwargs):
            raise RuntimeError("simulated failure")

        BotRequestHandler.service.handle_turn = boom  # type: ignore[assignment]
        try:
            create_req = request.Request("http://127.0.0.1:18081/v1/sessions", method="POST")
            with request.urlopen(create_req) as create_resp:
                session_id = json.loads(create_resp.read().decode("utf-8"))["session_id"]

            body = json.dumps({"text": "hello"}).encode("utf-8")
            turn_req = request.Request(
                f"http://127.0.0.1:18081/v1/sessions/{session_id}/turns",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(HTTPError) as raised:
                request.urlopen(turn_req)
            self.assertEqual(raised.exception.code, 500)
        finally:
            BotRequestHandler.service.handle_turn = original  # type: ignore[assignment]

    def test_unreadable_drift_report_is_handled(self) -> None:
        os.makedirs(os.path.dirname(settings.drift_report_path), exist_ok=True)
        with open(settings.drift_report_path, "w", encoding="utf-8") as handle:
            handle.write("not-json\n")

        drift_req = request.Request(
            "http://127.0.0.1:18081/v1/admin/drift-report",
            headers={"X-Role": "supervisor"},
        )
        with request.urlopen(drift_req) as response:
            self.assertEqual(response.status, 200)
            payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["status"], "drift report unreadable")


if __name__ == "__main__":
    unittest.main()
