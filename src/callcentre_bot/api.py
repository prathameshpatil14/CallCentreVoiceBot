import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from .assistant import VoiceSalesAssistantService
from .models import SessionCreateResponse, UserTurnRequest


class BotRequestHandler(BaseHTTPRequestHandler):
    service = VoiceSalesAssistantService()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return

        if path.startswith("/v1/sessions/"):
            session_id = path.removeprefix("/v1/sessions/")
            try:
                parsed_id = UUID(session_id)
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid session id"})
                return

            session = self.service.sessions.get(parsed_id)
            if session is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "session not found"})
                return

            self._send_json(HTTPStatus.OK, session.to_dict())
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/v1/sessions":
            session = SessionCreateResponse(session_id=uuid4())
            self.service.sessions.create(session.session_id)
            self._send_json(HTTPStatus.CREATED, session.to_dict())
            return

        if path.startswith("/v1/sessions/") and path.endswith("/turns"):
            session_id = path.removeprefix("/v1/sessions/").removesuffix("/turns")
            session_id = session_id.strip("/")
            try:
                parsed_id = UUID(session_id)
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid session id"})
                return

            payload = self._read_json_body()
            if payload is None:
                return

            request = UserTurnRequest.from_dict(payload)
            if not request.text:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "text cannot be empty"})
                return

            reply = self.service.handle_turn(session_id=parsed_id, text=request.text)
            self._send_json(HTTPStatus.OK, reply.to_dict())
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def _read_json_body(self) -> dict[str, Any] | None:
        raw_content_length = self.headers.get("Content-Length", "0")
        try:
            content_length = int(raw_content_length)
        except (TypeError, ValueError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid content-length"})
            return None
        if content_length < 0:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid content-length"})
            return None
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid json"})
            return None
        if not isinstance(payload, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "json body must be an object"})
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
