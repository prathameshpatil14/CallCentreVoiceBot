# CallCentreVoiceBot - Standard-Library Production Service

This codebase provides a production-oriented contact-center assistant backend with **in-house text models** and **no third-party APIs/models**.

## What changed

- Removed framework/model dependencies (no FastAPI, no external LLM API, no third-party ML).
- Added custom Naive Bayes classifiers implemented from scratch for:
  - intent classification,
  - sentiment classification.
- Added a standard-library HTTP server with JSON endpoints.
- Kept thread-safe session management, escalation controls, and deterministic product/FAQ handling.

## API endpoints

- `GET /health`
- `POST /v1/sessions`
- `GET /v1/sessions/{session_id}`
- `POST /v1/sessions/{session_id}/turns`

## Run

```bash
python -m venv .venv
source .venv/bin/activate
python -m callcentre_bot.main
```

Server defaults to `0.0.0.0:8080`.

## Example

```bash
curl -X POST http://localhost:8080/v1/sessions
curl -X POST http://localhost:8080/v1/sessions/<SESSION_ID>/turns \
  -H "Content-Type: application/json" \
  -d '{"text":"I want to buy a family mobile plan"}'
```

## Environment variables

- `BOT_NAME` (default: `Ava`)
- `CONFIDENCE_THRESHOLD` (default: `0.62`)
- `NEGATIVE_SENTIMENT_ESCALATION_TURNS` (default: `3`)
- `SERVER_HOST` (default: `0.0.0.0`)
- `SERVER_PORT` (default: `8080`)

## Notes

- This version uses human-like responses, but does not claim true human consciousness/emotions.
- To improve accuracy further, expand local training data in `src/callcentre_bot/nlu.py` and knowledge in `src/callcentre_bot/knowledge.py`.
