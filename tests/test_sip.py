import base64
import json
import threading
import time
import unittest
from urllib import request
from urllib.error import HTTPError

from callcentre_bot.api import create_http_server


class SipIngressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = create_http_server("127.0.0.1", 18082)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def _start_call(self) -> str:
        body = json.dumps(
            {
                "sip_headers": {
                    "X-ANI": "+15551234567",
                    "X-DNIS": "+18005550100",
                    "X-Account-ID": "ACC-991",
                    "X-Campaign": "retention",
                    "X-Transfer-Queue": "premium-care",
                }
            }
        ).encode("utf-8")
        req = request.Request(
            "http://127.0.0.1:18082/v1/sip/calls/start",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["campaign"], "retention")
        self.assertEqual(payload["account_id"], "ACC-991")
        return payload["call_id"]

    def test_sip_call_lifecycle_and_transfer(self) -> None:
        call_id = self._start_call()

        media_payload = json.dumps(
            {
                "audio_base64": base64.b64encode(b"I need billing support").decode("ascii"),
                "sample_rate_hz": 16000,
            }
        ).encode("utf-8")
        media_req = request.Request(
            f"http://127.0.0.1:18082/v1/sip/calls/{call_id}/media",
            data=media_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(media_req) as media_resp:
            media = json.loads(media_resp.read().decode("utf-8"))
        self.assertIn("text", media)

        dtmf_payload = json.dumps({"digit": "5"}).encode("utf-8")
        dtmf_req = request.Request(
            f"http://127.0.0.1:18082/v1/sip/calls/{call_id}/dtmf",
            data=dtmf_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(dtmf_req) as dtmf_resp:
            dtmf = json.loads(dtmf_resp.read().decode("utf-8"))
        self.assertEqual(dtmf["status"], "dtmf_received")

        hold_req = request.Request(f"http://127.0.0.1:18082/v1/sip/calls/{call_id}/hold", method="POST")
        with request.urlopen(hold_req) as hold_resp:
            hold = json.loads(hold_resp.read().decode("utf-8"))
        self.assertEqual(hold["status"], "on_hold")

        resume_req = request.Request(f"http://127.0.0.1:18082/v1/sip/calls/{call_id}/resume", method="POST")
        with request.urlopen(resume_req) as resume_resp:
            resume = json.loads(resume_resp.read().decode("utf-8"))
        self.assertEqual(resume["status"], "active")

        transfer_payload = json.dumps({"reason": "customer_requested_agent"}).encode("utf-8")
        transfer_req = request.Request(
            f"http://127.0.0.1:18082/v1/sip/calls/{call_id}/transfer",
            data=transfer_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(transfer_req) as transfer_resp:
            transfer = json.loads(transfer_resp.read().decode("utf-8"))
        self.assertEqual(transfer["status"], "transfer_initiated")
        self.assertEqual(transfer["dialer_payload"]["campaign"], "retention")

    def test_media_failover_after_retries(self) -> None:
        call_id = self._start_call()

        bad_media = json.dumps({"audio_base64": "not-valid", "sample_rate_hz": 16000}).encode("utf-8")
        for _ in range(2):
            req = request.Request(
                f"http://127.0.0.1:18082/v1/sip/calls/{call_id}/media",
                data=bad_media,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(HTTPError) as raised:
                request.urlopen(req)
            self.assertEqual(raised.exception.code, 502)

        get_req = request.Request(f"http://127.0.0.1:18082/v1/sip/calls/{call_id}")
        with request.urlopen(get_req) as get_resp:
            state = json.loads(get_resp.read().decode("utf-8"))
        self.assertEqual(state["retry_count"], 2)
        self.assertEqual(state["failover_gateway"], "secondary")


if __name__ == "__main__":
    unittest.main()
