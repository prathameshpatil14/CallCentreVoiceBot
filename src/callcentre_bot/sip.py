from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import base64
from threading import Lock
from typing import Any
from uuid import UUID, uuid4

from .assistant import VoiceSalesAssistantService


@dataclass
class SipCallState:
    call_id: str
    session_id: UUID
    ani: str = ""
    dnis: str = ""
    account_id: str = ""
    campaign: str = "default"
    transfer_metadata: dict[str, str] = field(default_factory=dict)
    status: str = "active"
    hold: bool = False
    retry_count: int = 0
    failover_gateway: str = "primary"
    last_error: str = ""
    started_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SipHeaderMapper:
    def map_context(self, headers: dict[str, str]) -> dict[str, Any]:
        normalized = {str(k).strip().lower(): str(v).strip() for k, v in headers.items()}

        ani = normalized.get("x-ani") or normalized.get("from") or normalized.get("p-asserted-identity", "")
        dnis = normalized.get("x-dnis") or normalized.get("to", "")
        account_id = normalized.get("x-account-id", "")
        campaign = normalized.get("x-campaign", "default") or "default"

        transfer_metadata = {
            "queue": normalized.get("x-transfer-queue", ""),
            "agent": normalized.get("x-agent-id", ""),
            "uui": normalized.get("x-uui", ""),
        }
        return {
            "ani": ani,
            "dnis": dnis,
            "account_id": account_id,
            "campaign": campaign,
            "transfer_metadata": transfer_metadata,
        }


class RtpMediaBridge:
    def __init__(self, assistant: VoiceSalesAssistantService) -> None:
        self.assistant = assistant

    def process_audio(self, call: SipCallState, audio_base64: str, sample_rate_hz: int, request_id: str) -> dict[str, Any]:
        audio_bytes = base64.b64decode(audio_base64, validate=True)
        response = self.assistant.handle_voice_turn(
            session_id=call.session_id,
            request_id=request_id,
            audio_bytes=audio_bytes,
            sample_rate_hz=sample_rate_hz,
        )
        call.updated_at_utc = datetime.now(timezone.utc).isoformat()
        return response.to_dict()


class TransferOrchestrator:
    def handoff_payload(self, call: SipCallState, reason: str) -> dict[str, Any]:
        call.status = "transferred"
        call.updated_at_utc = datetime.now(timezone.utc).isoformat()
        return {
            "status": "transfer_initiated",
            "call_id": call.call_id,
            "session_id": str(call.session_id),
            "reason": reason,
            "dialer_payload": {
                "ani": call.ani,
                "dnis": call.dnis,
                "account_id": call.account_id,
                "campaign": call.campaign,
                "transfer_metadata": call.transfer_metadata,
            },
        }


class SipIngressService:
    def __init__(self, assistant: VoiceSalesAssistantService) -> None:
        self.assistant = assistant
        self.mapper = SipHeaderMapper()
        self.media = RtpMediaBridge(assistant)
        self.transfer = TransferOrchestrator()
        self._calls: dict[str, SipCallState] = {}
        self._lock = Lock()

    def start_call(self, sip_headers: dict[str, str], call_id: str | None = None) -> SipCallState:
        context = self.mapper.map_context(sip_headers)
        session_id = uuid4()
        self.assistant.sessions.create(session_id)
        self.assistant.apply_external_context(
            session_id=session_id,
            account_id=context["account_id"],
            campaign=context["campaign"],
            ani=context["ani"],
            dnis=context["dnis"],
            transfer_metadata=context["transfer_metadata"],
        )

        call = SipCallState(
            call_id=call_id or str(uuid4()),
            session_id=session_id,
            ani=context["ani"],
            dnis=context["dnis"],
            account_id=context["account_id"],
            campaign=context["campaign"],
            transfer_metadata=context["transfer_metadata"],
        )
        with self._lock:
            self._calls[call.call_id] = call
        return call

    def get_call(self, call_id: str) -> SipCallState | None:
        with self._lock:
            return self._calls.get(call_id)

    def process_media(self, call_id: str, *, audio_base64: str, sample_rate_hz: int, request_id: str) -> dict[str, Any]:
        call = self.get_call(call_id)
        if call is None:
            raise KeyError("call not found")
        if call.hold:
            return {
                "status": "on_hold",
                "call_id": call.call_id,
                "message": "Media paused while call is on hold",
            }

        try:
            return self.media.process_audio(call, audio_base64, sample_rate_hz, request_id)
        except Exception as exc:
            call.retry_count += 1
            call.last_error = str(exc)
            if call.retry_count >= 2:
                call.failover_gateway = "secondary"
            call.updated_at_utc = datetime.now(timezone.utc).isoformat()
            raise

    def dtmf_event(self, call_id: str, digit: str) -> dict[str, Any]:
        call = self.get_call(call_id)
        if call is None:
            raise KeyError("call not found")
        call.updated_at_utc = datetime.now(timezone.utc).isoformat()
        return {
            "status": "dtmf_received",
            "call_id": call.call_id,
            "digit": digit,
        }

    def hold_call(self, call_id: str) -> dict[str, Any]:
        call = self.get_call(call_id)
        if call is None:
            raise KeyError("call not found")
        call.hold = True
        call.status = "on_hold"
        call.updated_at_utc = datetime.now(timezone.utc).isoformat()
        return {"status": "on_hold", "call_id": call.call_id}

    def resume_call(self, call_id: str) -> dict[str, Any]:
        call = self.get_call(call_id)
        if call is None:
            raise KeyError("call not found")
        call.hold = False
        call.status = "active"
        call.updated_at_utc = datetime.now(timezone.utc).isoformat()
        return {"status": "active", "call_id": call.call_id}

    def transfer_call(self, call_id: str, reason: str) -> dict[str, Any]:
        call = self.get_call(call_id)
        if call is None:
            raise KeyError("call not found")
        return self.transfer.handoff_payload(call, reason)

    @staticmethod
    def serialize_call(call: SipCallState) -> dict[str, Any]:
        return {
            "call_id": call.call_id,
            "session_id": str(call.session_id),
            "ani": call.ani,
            "dnis": call.dnis,
            "account_id": call.account_id,
            "campaign": call.campaign,
            "transfer_metadata": call.transfer_metadata,
            "status": call.status,
            "hold": call.hold,
            "retry_count": call.retry_count,
            "failover_gateway": call.failover_gateway,
            "last_error": call.last_error,
            "started_at_utc": call.started_at_utc,
            "updated_at_utc": call.updated_at_utc,
        }
