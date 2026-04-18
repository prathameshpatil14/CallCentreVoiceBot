# Production Readiness Roadmap

This document lists the highest-priority improvements for the current in-house CallCentreVoiceBot.

## 1) Accuracy and model quality (Highest priority)

Current intent/sentiment models are basic Naive Bayes trained on small samples.

### Improvements
- Build a larger internal labeled dataset from real call transcripts.
- Add language normalization for spelling mistakes and Hinglish/vernacular patterns.
- Add an offline evaluation pipeline (precision/recall/F1, confusion matrices).
- Version and A/B test model artifacts before rollout.

## 2) Conversation quality

### Improvements
- Add context memory (customer name, account type, previous unresolved issues).
- Add configurable conversation flows per campaign/product.
- Add a confidence-aware clarification strategy before escalation.
- Add policy guardrails for compliance phrases and restricted claims.

## 3) Persistence and reliability

Current session store is in-memory.

### Improvements
- Replace in-memory sessions with durable storage (SQLite/PostgreSQL).
- Add request IDs and structured JSON logs.
- Add graceful restart and health probes for service supervisors.
- Add rate limiting and request size limits.

## 4) Voice stack completeness

Current ASR/TTS are interfaces only.

### Improvements
- Implement in-house/offline ASR and TTS modules.
- Add barge-in handling and voice activity detection.
- Add latency budget tracking (ASR + policy + TTS total response time).

## 5) Security and operations

### Improvements
- Add authentication and authorization for API endpoints.
- Add PII redaction in logs and transcript storage encryption.
- Add monitoring dashboards (latency, error rate, escalation rate).
- Add load testing and chaos testing before production launch.

## 6) Hardware feasibility

### Can this run on 16 GB RAM + Intel i5 13th gen?
Yes — the current version is lightweight and should run comfortably on that machine for development and low-to-moderate traffic.

### Expected profile
- RAM usage: typically low (few hundred MB range) for this codebase.
- CPU usage: modest for text-only NLU; increases once ASR/TTS are added.
- Suitable for: local dev, QA, pilot deployments.

### When you need stronger hardware
- High concurrent call volume.
- Real-time local ASR/TTS or larger custom models.
- Multi-language acoustic models with strict low latency requirements.

### Suggested local run settings
- Run 2–4 worker processes behind a reverse proxy.
- Keep model artifacts in memory and pre-warm on startup.
- Persist sessions to disk/DB to survive restarts.
