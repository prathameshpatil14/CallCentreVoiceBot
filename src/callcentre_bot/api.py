from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status

from .assistant import VoiceSalesAssistantService
from .models import AssistantTurnResponse, SessionCreateResponse, SessionState, UserTurnRequest

router = APIRouter(prefix="/v1", tags=["assistant"])
service = VoiceSalesAssistantService()


@router.post("/sessions", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_session() -> SessionCreateResponse:
    session = SessionCreateResponse(session_id=uuid4())
    service.sessions.create(session.session_id)
    return session


@router.get("/sessions/{session_id}", response_model=SessionState)
def get_session(session_id: UUID) -> SessionState:
    state = service.sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return state


@router.post("/sessions/{session_id}/turns", response_model=AssistantTurnResponse)
def process_turn(session_id: UUID, payload: UserTurnRequest) -> AssistantTurnResponse:
    if len(payload.text.strip()) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="text cannot be empty")
    return service.handle_turn(session_id=session_id, text=payload.text)
