# Full Voice Bot Implementation Checklist

Use this as a practical verification sheet for production review.

## Core capability checklist

- [x] Intent and sentiment modelling with train/validation/test discipline.
- [x] NLU normalization for spelling/Hinglish variants.
- [x] Per-intent confidence thresholds and confidence-aware clarifications.
- [x] Policy reranking for selecting best response/action.
- [x] Journey state machine (`sell`, `upsell`, `complaint`, `refund`, `general`).
- [x] Campaign-aware flow constraints and mandatory disclaimers.
- [x] Compliance guardrails for restricted claims/phrases.
- [x] Session context memory (`customer_name`, account and issue context).
- [x] Human-like consciousness behavior:
  - [x] emotion mirroring for negative/positive user sentiment.
  - [x] customer-name recall to personalize multi-turn responses.
  - [x] transparent human handoff language on escalation.

## Reliability and operations checklist

- [x] Durable persistence for sessions + turns (SQLite / optional PostgreSQL).
- [x] Background archival and retention workflow.
- [x] Request IDs, structured logging, and PII redaction.
- [x] Health probes (`/health`, `/health/live`, `/health/ready`).
- [x] Rate limiting and payload-size protection.
- [x] Drift monitoring and weekly persisted drift snapshots.
- [x] Metrics endpoint with operational counters and latency observations.

## Voice layer checklist

- [x] Offline ASR/TTS placeholders.
- [x] Basic voice activity detection helper.
- [ ] Production-grade speech stack (advanced ASR/TTS quality and latency tuning) pending.

## Security checklist

- [x] API key auth with rotation support.
- [x] Role-based access for supervisory endpoints.
- [x] Optional TLS enforcement (`REQUIRE_TLS=true` behind reverse proxy).

## Suggested final verification before go-live

- [ ] Load testing at expected peak concurrency.
- [ ] Automated chaos/failure injection tests.
- [ ] Real-call quality review for tone, compliance, and escalation precision.
