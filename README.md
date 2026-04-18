# CallCentreVoiceBot - Production Service

This repository now contains a **production-oriented backend service** for a contact-center sales and support assistant.

## What is production-ready in this version

- FastAPI HTTP service with health and conversation endpoints.
- Configuration through environment variables (`pydantic-settings`).
- Thread-safe in-memory session state store.
- Structured request/response schemas with validation.
- Deterministic policy layer for:
  - product sales guidance,
  - FAQ/support responses,
  - sentiment-aware language,
  - explicit handoff decisions.
- Pluggable interfaces for ASR/TTS and NLU providers.
- Unit + API tests via `pytest`.

> Note: no system can have true human thinking or feelings. This service provides **human-like interaction behavior** with escalation controls.

---

## API endpoints

- `GET /health` - health check.
- `POST /v1/sessions` - create a conversation session.
- `POST /v1/sessions/{session_id}/turns` - process one user utterance and return a bot response.
- `GET /v1/sessions/{session_id}` - inspect session state.

---

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn callcentre_bot.main:app --reload --host 0.0.0.0 --port 8000
```

## Example request

```bash
curl -X POST http://localhost:8000/v1/sessions

curl -X POST http://localhost:8000/v1/sessions/<SESSION_ID>/turns \
  -H "Content-Type: application/json" \
  -d '{"text":"I want to buy a family mobile plan"}'
```

---

## Environment variables

- `BOT_NAME` (default: `Ava`)
- `CONFIDENCE_THRESHOLD` (default: `0.62`)
- `NEGATIVE_SENTIMENT_ESCALATION_TURNS` (default: `3`)

---

## Production integration points

- Replace `RuleBasedNLUEngine` with an LLM/NLU service.
- Replace `NullASRAdapter` and `NullTTSAdapter` with live voice providers.
- Connect `KnowledgeRepository` to a database/vector store + CRM/order APIs.
- Add persistent storage and distributed cache for horizontal scaling.
