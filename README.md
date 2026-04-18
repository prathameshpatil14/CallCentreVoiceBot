# CallCentreVoiceBot (Python Starter)

This repository contains a practical starter implementation for a **voice contact-center chatbot**.

## What this bot can do

- Handle basic customer conversations in text or voice pipelines.
- Detect customer sentiment (`positive`, `neutral`, `negative`) and adapt tone.
- Answer FAQs from a local knowledge base.
- Run a guided sales flow for products.
- Escalate difficult/unclear cases to a human agent.

> Important: no AI system has true human thinking or emotions. This starter aims for **human-like conversational behavior**, not consciousness.

---

## Architecture

The `VoiceSalesAssistant` combines modular components:

1. **ASR (speech-to-text)**: convert caller audio to text.
2. **Intent + sentiment**: classify user goal and emotional tone.
3. **Knowledge + product retrieval**: fetch FAQ answers and product details.
4. **Dialog policy**: decide whether to answer, sell, clarify, or escalate.
5. **TTS (text-to-speech)**: return voice response.

In this starter, ASR/TTS are pluggable stubs and text-mode simulation is fully runnable.

---

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_demo.py
```

Then type customer messages in terminal. Type `exit` to stop.

---

## Files

- `src/callcentre_bot/assistant.py` - orchestration logic.
- `src/callcentre_bot/dialog.py` - intent handling + response strategy.
- `src/callcentre_bot/knowledge.py` - FAQ + product catalog lookup.
- `src/callcentre_bot/sentiment.py` - simple sentiment detector.
- `src/callcentre_bot/voice.py` - ASR/TTS adapter interfaces.
- `run_demo.py` - CLI demo.

---

## Next production upgrades

1. Replace rule-based sentiment/intent with LLM + classifier.
2. Add multilingual support (e.g., English/Hindi).
3. Add CRM integration and order creation APIs.
4. Add call recording, compliance scripts, and audit logging.
5. Add confidence thresholds and forced human handoff for risk cases.
