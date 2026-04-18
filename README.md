# CallCentreVoiceBot - Production-Oriented In-House Assistant

A contact-center sales/support assistant with **no third-party API/model dependency**.

## Implemented roadmap items

1. **Accuracy/model quality**
   - Larger local labeled dataset in `src/callcentre_bot/data/*.jsonl`.
   - Text normalization for spelling/Hinglish terms in NLU.
   - Offline evaluation script with precision/recall/F1/confusion matrix (`scripts/evaluate_models.py`).
   - Model version/variant support via `MODEL_VARIANT`.

2. **Conversation quality**
   - Context memory in session state (`customer_name`, `account_type`, unresolved issues, campaign).
   - Campaign-specific conversation flows + disclaimers.
   - Confidence-aware clarification prompts.
   - Compliance guardrails for restricted phrases.

3. **Persistence/reliability**
   - Durable SQLite-backed sessions + turn history.
   - Request IDs and structured logs with PII redaction.
   - Graceful shutdown and health probes (`/health`, `/health/live`, `/health/ready`).
   - Request rate limiting and payload-size guardrails.

4. **Voice stack completeness**
   - In-house offline ASR/TTS placeholders.
   - Basic voice activity detection helper.

5. **Security/operations**
   - Optional API key auth using `X-API-Key`.
   - Metrics endpoint (`/metrics`) with request and latency counters.

## API endpoints

- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- `GET /metrics`
- `POST /v1/sessions`
- `GET /v1/sessions/{session_id}`
- `POST /v1/sessions/{session_id}/turns`

## Run

```bash
python -m venv .venv
source .venv/bin/activate
python -m callcentre_bot.main
```

## Evaluate in-house models

```bash
python scripts/evaluate_models.py
```

## Environment variables

- `BOT_NAME` (default `Ava`)
- `CONFIDENCE_THRESHOLD` (default `0.62`)
- `NEGATIVE_SENTIMENT_ESCALATION_TURNS` (default `3`)
- `SERVER_HOST` (default `0.0.0.0`)
- `SERVER_PORT` (default `8080`)
- `SQLITE_PATH` (default `callcentre.db`)
- `API_KEY` (optional; if set, `X-API-Key` required)
- `MAX_REQUEST_BYTES` (default `32768`)
- `RATE_LIMIT_PER_MINUTE` (default `120`)
- `MODEL_VARIANT` (default `A`; supports simple A/B behavior)
