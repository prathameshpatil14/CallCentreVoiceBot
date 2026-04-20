# CallCentreVoiceBot - Production-Oriented In-House Assistant

A contact-center sales/support assistant with **no third-party API/model dependency**.

## Implemented roadmap items

1. **Accuracy/model quality**
   - Strict train/validation/test datasets (`intent_*.jsonl`, `sentiment_*.jsonl`).
   - Text normalization for spelling/Hinglish terms in NLU.
   - Per-intent confidence thresholds (sales/support/escalation/refund/upsell).
   - Offline evaluation script with precision/recall/F1/confusion matrix on held-out test split (`scripts/evaluate_models.py`).
   - Model version/variant support via `MODEL_VARIANT`.
   - Drift monitor comparing production intent distribution vs training baseline.
   - Validation-set-based threshold calibration + persisted weekly drift reports.

2. **Conversation quality**
   - Context memory in session state (`customer_name`, `account_id`, `account_type`, issues, campaign).
   - Explicit journey state machine (`sell`, `upsell`, `complaint`, `refund`).
   - Campaign-specific conversation flows + disclaimers.
   - Confidence-aware clarification prompts + deterministic transfer policy (clarification/retry caps).
   - Lightweight policy reranker to choose best template/action from candidates.
   - Compliance guardrails for restricted phrases.
   - Human-like consciousness layer (emotion mirroring + customer-name recall for personalized responses).

3. **Persistence/reliability**
   - Durable SQLite-backed sessions + turn history with optional PostgreSQL backend.
   - Background archival + retention policy for turn logs.
   - Request IDs and structured logs with PII redaction.
   - Graceful shutdown and health probes (`/health`, `/health/live`, `/health/ready`).
   - Request rate limiting and payload-size guardrails.

4. **Voice stack completeness**
   - In-house offline ASR/TTS placeholders.
   - Basic voice activity detection helper.

5. **Security/operations**
   - API key auth with key rotation (`API_KEYS` comma list) and audit trails.
   - Basic role-based access for metrics endpoint (`X-Role`).
   - Expanded PII redaction (PAN/Aadhaar/account variants).
   - Optional TLS enforcement through reverse proxy (`REQUIRE_TLS=true`).
   - Metrics endpoint (`/metrics`) with request, latency, and drift counters.
   - Supervisor drift report endpoint (`/v1/admin/drift-report`).

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


## What these two APIs do

### `GET /v1/sessions/{session_id}`
Use this to fetch the **current conversation state** for a specific session.

It returns things like:
- total turns,
- latest intent/sentiment,
- whether escalation happened,
- captured context (customer name/account type/campaign).

You use this when dashboards/agents need to inspect a live call session.

### `POST /v1/sessions/{session_id}/turns`
Use this to send **one new customer utterance** to the bot for that session.

Flow:
1. You send JSON: `{"text": "customer message"}`.
2. Bot runs NLU + policy + knowledge lookup.
3. Bot updates session memory/persistence.
4. API returns bot reply + intent/sentiment/confidence + escalation flag.

This is the main endpoint that drives the conversation turn-by-turn.
