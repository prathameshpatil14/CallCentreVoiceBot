# Production Readiness Roadmap Status

This file tracks roadmap implementation status.

## 1) Accuracy and model quality
- ✅ Strict train/validation/test split added for intent + sentiment datasets.
- ✅ Normalization added for spelling and Hinglish tokens.
- ✅ Per-intent confidence thresholds added (sales/support/escalation/refund/upsell).
- ✅ Offline evaluation pipeline implemented on held-out test split (`scripts/evaluate_models.py`).
- ✅ Model versioning + variant switch (`MODEL_VARIANT=A/B`) added.
- ✅ Weekly drift monitoring support added (`/metrics` drift keys).
- ✅ Weekly drift snapshots are persisted for operational review (`DRIFT_REPORT_PATH`).

## 2) Conversation quality
- ✅ Context extraction improved with regex parsing (`name`, `account_id`, issue summary).
- ✅ Journey state machine added (`sell`, `upsell`, `complaint`, `refund`).
- ✅ Campaign-specific flows with disclaimers added.
- ✅ Confidence-aware clarification path implemented.
- ✅ Deterministic transfer policy via clarification/retry counters.
- ✅ Policy reranker added for candidate response/action selection.
- ✅ Compliance guardrails for restricted phrases added.

## 3) Persistence and reliability
- ✅ Durable SQLite persistence for sessions + turns added.
- ✅ Optional PostgreSQL backend added for concurrent production deployment.
- ✅ Background archival + retention policy added (`turns_archive`, retention cutoff).
- ✅ Structured logs and request IDs added.
- ✅ Health/live/ready probes and graceful shutdown added.
- ✅ Rate limiting + request payload size limit added.

## 4) Voice stack completeness
- ✅ In-house/offline ASR/TTS placeholders implemented.
- ✅ Basic voice activity detector added.
- ⚠️ Full production-grade speech recognition/synthesis still requires substantial internal DSP/modeling work.

## 5) Security and operations
- ✅ API key authentication with key rotation support added.
- ✅ Basic role-based access + audit trail events added.
- ✅ PII redaction for logged transcripts expanded (PAN/Aadhaar/account variants).
- ✅ Optional TLS enforcement for reverse-proxy deployments added.
- ✅ Metrics endpoint for latency/error/escalation and drift counters added.
- ✅ Supervisor drift report endpoint added (`/v1/admin/drift-report`).
- ⚠️ Full load/chaos testing automation still pending and should be added before launch.
