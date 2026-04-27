import json
import base64
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from .assistant import VoiceSalesAssistantService
from .config import settings
from .models import SessionCreateResponse, UserTurnRequest
from .rate_limit import SlidingWindowRateLimiter
from .sip import SipIngressService


class BotRequestHandler(BaseHTTPRequestHandler):
    service = VoiceSalesAssistantService()
    limiter = SlidingWindowRateLimiter(settings.rate_limit_per_minute)
    sip = SipIngressService(service)

    def _request_id(self) -> str:
        return self.headers.get("X-Request-ID", str(uuid4()))

    def _authorized(self) -> bool:
        keys = set(settings.valid_api_keys)
        if settings.api_key:
            keys.add(settings.api_key)
        if not keys:
            return True
        return self.headers.get("X-API-Key", "") in keys

    def _role(self) -> str:
        return self.headers.get("X-Role", "agent").strip().lower()

    def _has_role(self, required: str) -> bool:
        rank = {"agent": 1, "supervisor": 2, "admin": 3}
        return rank.get(self._role(), 0) >= rank.get(required, 1)

    def _tls_ok(self) -> bool:
        if not settings.require_tls:
            return True
        return self.headers.get("X-Forwarded-Proto", "").lower() == "https"

    def _rate_limited(self) -> bool:
        client = self.client_address[0]
        return not self.limiter.allow(client)

    def do_GET(self) -> None:  # noqa: N802
        try:
            self._do_get_impl()
        except Exception:
            request_id = self._request_id()
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal server error", "request_id": request_id})

    def _do_get_impl(self) -> None:
        request_id = self._request_id()
        parsed = urlparse(self.path)
        path = parsed.path

        if not self._tls_ok():
            self._send_json(HTTPStatus.UPGRADE_REQUIRED, {"error": "tls required", "request_id": request_id})
            return

        if path in {"/health", "/health/live", "/health/ready"}:
            self._send_json(HTTPStatus.OK, {"status": "ok", "request_id": request_id})
            return

        if path == "/metrics":
            if not self._has_role(settings.role_required_for_metrics):
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "insufficient role", "request_id": request_id})
                return
            payload = self.service.metrics.snapshot() | self.service.drift.snapshot()
            self._send_json(HTTPStatus.OK, payload | {"request_id": request_id})
            return

        if path == "/v1/admin/drift-report":
            if not self._has_role("supervisor"):
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "insufficient role", "request_id": request_id})
                return
            report = self._load_latest_drift_report()
            self._send_json(HTTPStatus.OK, report | {"request_id": request_id})
            return

        if path.startswith("/v1/sip/calls/"):
            if not self._authorized():
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized", "request_id": request_id})
                return
            call_id = path.removeprefix("/v1/sip/calls/").strip("/")
            call = self.sip.get_call(call_id)
            if call is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "call not found", "request_id": request_id})
                return
            self._send_json(HTTPStatus.OK, self.sip.serialize_call(call) | {"request_id": request_id})
            return

        if not self._authorized():
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized", "request_id": request_id})
            return

        if path.startswith("/v1/sessions/"):
            session_id = path.removeprefix("/v1/sessions/")
            try:
                parsed_id = UUID(session_id)
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid session id", "request_id": request_id})
                return

            session = self.service.sessions.get(parsed_id)
            if session is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "session not found", "request_id": request_id})
                return

            payload = session.to_dict()
            payload["request_id"] = request_id
            self._send_json(HTTPStatus.OK, payload)
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found", "request_id": request_id})

    def do_POST(self) -> None:  # noqa: N802
        try:
            self._do_post_impl()
        except Exception:
            request_id = self._request_id()
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal server error", "request_id": request_id})

    def _do_post_impl(self) -> None:
        request_id = self._request_id()
        if not self._tls_ok():
            self._send_json(HTTPStatus.UPGRADE_REQUIRED, {"error": "tls required", "request_id": request_id})
            return

        if self._rate_limited():
            self._send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "rate limit exceeded", "request_id": request_id})
            return

        if not self._authorized():
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized", "request_id": request_id})
            return

        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/v1/sessions":
            session = SessionCreateResponse(session_id=uuid4())
            self.service.sessions.create(session.session_id)
            payload = session.to_dict() | {"request_id": request_id}
            self._send_json(HTTPStatus.CREATED, payload)
            return

        if path == "/v1/sip/calls/start":
            payload = self._read_json_body(request_id)
            if payload is None:
                return
            sip_headers = payload.get("sip_headers", {})
            if not isinstance(sip_headers, dict):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "sip_headers must be an object", "request_id": request_id})
                return
            call_id = str(payload.get("call_id", "")).strip() or None
            call = self.sip.start_call(sip_headers={str(k): str(v) for k, v in sip_headers.items()}, call_id=call_id)
            self._send_json(
                HTTPStatus.CREATED,
                self.sip.serialize_call(call) | {"request_id": request_id},
            )
            return

        if path.startswith("/v1/sessions/") and path.endswith("/turns"):
            session_id = path.removeprefix("/v1/sessions/").removesuffix("/turns")
            session_id = session_id.strip("/")
            try:
                parsed_id = UUID(session_id)
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid session id", "request_id": request_id})
                return

            payload = self._read_json_body(request_id)
            if payload is None:
                return

            request_payload = UserTurnRequest.from_dict(payload)
            if not request_payload.text:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "text cannot be empty", "request_id": request_id})
                return

            reply = self.service.handle_turn(session_id=parsed_id, request_id=request_id, text=request_payload.text)
            self._send_json(HTTPStatus.OK, reply.to_dict())
            return

        if path.startswith("/v1/sip/calls/") and path.endswith("/media"):
            call_id = path.removeprefix("/v1/sip/calls/").removesuffix("/media").strip("/")
            payload = self._read_json_body(request_id)
            if payload is None:
                return
            audio_base64 = str(payload.get("audio_base64", "")).strip()
            if not audio_base64:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "audio_base64 is required", "request_id": request_id})
                return
            try:
                sample_rate_hz = int(payload.get("sample_rate_hz", 16000))
            except (TypeError, ValueError):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "sample_rate_hz must be an integer", "request_id": request_id})
                return
            try:
                reply = self.sip.process_media(
                    call_id=call_id,
                    audio_base64=audio_base64,
                    sample_rate_hz=sample_rate_hz,
                    request_id=request_id,
                )
            except KeyError:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "call not found", "request_id": request_id})
                return
            except Exception as exc:
                self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "media bridge failure", "detail": str(exc), "request_id": request_id})
                return
            self._send_json(HTTPStatus.OK, reply | {"request_id": request_id})
            return

        if path.startswith("/v1/sip/calls/") and path.endswith("/dtmf"):
            call_id = path.removeprefix("/v1/sip/calls/").removesuffix("/dtmf").strip("/")
            payload = self._read_json_body(request_id)
            if payload is None:
                return
            digit = str(payload.get("digit", "")).strip()
            if not digit:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "digit is required", "request_id": request_id})
                return
            try:
                event = self.sip.dtmf_event(call_id, digit)
            except KeyError:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "call not found", "request_id": request_id})
                return
            self._send_json(HTTPStatus.OK, event | {"request_id": request_id})
            return

        if path.startswith("/v1/sip/calls/") and path.endswith("/hold"):
            call_id = path.removeprefix("/v1/sip/calls/").removesuffix("/hold").strip("/")
            try:
                event = self.sip.hold_call(call_id)
            except KeyError:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "call not found", "request_id": request_id})
                return
            self._send_json(HTTPStatus.OK, event | {"request_id": request_id})
            return

        if path.startswith("/v1/sip/calls/") and path.endswith("/resume"):
            call_id = path.removeprefix("/v1/sip/calls/").removesuffix("/resume").strip("/")
            try:
                event = self.sip.resume_call(call_id)
            except KeyError:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "call not found", "request_id": request_id})
                return
            self._send_json(HTTPStatus.OK, event | {"request_id": request_id})
            return

        if path.startswith("/v1/sip/calls/") and path.endswith("/transfer"):
            call_id = path.removeprefix("/v1/sip/calls/").removesuffix("/transfer").strip("/")
            payload = self._read_json_body(request_id)
            if payload is None:
                return
            reason = str(payload.get("reason", "requested")).strip()
            try:
                event = self.sip.transfer_call(call_id, reason)
            except KeyError:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "call not found", "request_id": request_id})
                return
            self._send_json(HTTPStatus.OK, event | {"request_id": request_id})
            return

        if path.startswith("/v1/sessions/") and path.endswith("/voice-turns"):
            session_id = path.removeprefix("/v1/sessions/").removesuffix("/voice-turns")
            session_id = session_id.strip("/")
            try:
                parsed_id = UUID(session_id)
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid session id", "request_id": request_id})
                return

            payload = self._read_json_body(request_id)
            if payload is None:
                return

            encoded_audio = str(payload.get("audio_base64", "")).strip()
            if not encoded_audio:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "audio_base64 is required", "request_id": request_id})
                return

            try:
                audio_bytes = base64.b64decode(encoded_audio, validate=True)
            except Exception:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "audio_base64 is invalid", "request_id": request_id})
                return

            try:
                sample_rate_hz = int(payload.get("sample_rate_hz", 16000))
            except (TypeError, ValueError):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "sample_rate_hz must be an integer", "request_id": request_id})
                return
            if sample_rate_hz < 8000 or sample_rate_hz > 48000:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "sample_rate_hz out of range", "request_id": request_id})
                return

            reply = self.service.handle_voice_turn(
                session_id=parsed_id,
                request_id=request_id,
                audio_bytes=audio_bytes,
                sample_rate_hz=sample_rate_hz,
            )
            self._send_json(HTTPStatus.OK, reply.to_dict())
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found", "request_id": request_id})

    def _read_json_body(self, request_id: str) -> dict[str, Any] | None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid content-length", "request_id": request_id})
            return None
        if content_length > settings.max_request_bytes:
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "payload too large", "request_id": request_id})
            return None

        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid json", "request_id": request_id})
            return None
        if not isinstance(payload, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "json body must be an object", "request_id": request_id})
            return None
        return payload

    def _send_json(self, status_code: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _load_latest_drift_report(self) -> dict[str, Any]:
        path = Path(settings.drift_report_path)
        if not path.exists():
            return {"status": "no drift reports yet"}
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            return {"status": "no drift reports yet"}
        try:
            payload = json.loads(lines[-1])
        except json.JSONDecodeError:
            return {"status": "drift report unreadable"}
        return {"status": "ok", "latest": payload}

    def log_message(self, format: str, *args: object) -> None:
        return


def create_http_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), BotRequestHandler)
