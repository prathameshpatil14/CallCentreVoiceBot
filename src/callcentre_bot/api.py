import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from .assistant import VoiceSalesAssistantService
from .config import settings
from .models import SessionCreateResponse, UserTurnRequest
from .rate_limit import SlidingWindowRateLimiter


class BotRequestHandler(BaseHTTPRequestHandler):
    service = VoiceSalesAssistantService()
    limiter = SlidingWindowRateLimiter(settings.rate_limit_per_minute)

    def _request_id(self) -> str:
        return self.headers.get("X-Request-ID", str(uuid4()))

    def _authorized(self) -> bool:
        if not settings.api_key:
            return True
        return self.headers.get("X-API-Key", "") == settings.api_key

    def _rate_limited(self) -> bool:
        client = self.client_address[0]
        return not self.limiter.allow(client)

    def do_GET(self) -> None:  # noqa: N802
        request_id = self._request_id()
        parsed = urlparse(self.path)
        path = parsed.path

        if path in {"/health", "/health/live", "/health/ready"}:
            self._send_json(HTTPStatus.OK, {"status": "ok", "request_id": request_id})
            return

        if path == "/metrics":
            self._send_json(HTTPStatus.OK, self.service.metrics.snapshot() | {"request_id": request_id})
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
        request_id = self._request_id()

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

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found", "request_id": request_id})

    def _read_json_body(self, request_id: str) -> dict[str, Any] | None:
        content_length = int(self.headers.get("Content-Length", "0"))
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

    def log_message(self, format: str, *args: object) -> None:
        return


def create_http_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), BotRequestHandler)
