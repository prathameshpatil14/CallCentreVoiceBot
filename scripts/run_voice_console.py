"""Local mic/speaker console for CallCentreVoiceBot.

Requires Linux `arecord` + `aplay` binaries.

Usage:
  PYTHONPATH=src python scripts/run_voice_console.py --base-url http://127.0.0.1:8080
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
from urllib import request


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def create_session(base_url: str) -> str:
    req = request.Request(f"{base_url}/v1/sessions", method="POST")
    with request.urlopen(req, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload["session_id"]


def capture_audio(sample_rate_hz: int, duration_seconds: int) -> bytes:
    cmd = [
        "arecord",
        "-q",
        "-f",
        "S16_LE",
        "-c",
        "1",
        "-r",
        str(sample_rate_hz),
        "-d",
        str(duration_seconds),
        "-t",
        "raw",
    ]
    completed = subprocess.run(cmd, capture_output=True, check=False)
    if completed.returncode != 0:
        return b""
    return completed.stdout


def play_audio(audio_bytes: bytes, sample_rate_hz: int) -> bool:
    cmd = [
        "aplay",
        "-q",
        "-f",
        "S16_LE",
        "-c",
        "1",
        "-r",
        str(sample_rate_hz),
    ]
    completed = subprocess.run(cmd, input=audio_bytes, capture_output=True, check=False)
    return completed.returncode == 0


def send_voice_turn(base_url: str, session_id: str, audio_bytes: bytes, sample_rate_hz: int) -> dict:
    payload = {
        "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
        "sample_rate_hz": sample_rate_hz,
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url}/v1/sessions/{session_id}/voice-turns",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def run_console(base_url: str, sample_rate_hz: int, duration_seconds: int) -> int:
    if not command_exists("arecord") or not command_exists("aplay"):
        print("This console currently requires Linux audio tools: arecord + aplay.")
        print("Install ALSA utils, or call /voice-turns from your own client.")
        return 2

    session_id = create_session(base_url)
    print(f"Voice console connected. Session: {session_id}")
    print("Press Enter to record one turn, or type q then Enter to quit.")

    while True:
        choice = input("> ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            print("Stopping voice console.")
            return 0

        print(f"Recording {duration_seconds}s...")
        audio = capture_audio(sample_rate_hz=sample_rate_hz, duration_seconds=duration_seconds)
        if not audio:
            print("Recording failed or empty input. Try again.")
            continue

        try:
            reply = send_voice_turn(base_url=base_url, session_id=session_id, audio_bytes=audio, sample_rate_hz=sample_rate_hz)
        except Exception as exc:
            print(f"Voice API request failed: {exc}")
            continue

        transcript = reply.get("transcript", "")
        text = reply.get("text", "")
        fallback = bool(reply.get("fallback_used", False))
        fallback_reason = str(reply.get("fallback_reason", ""))

        print(f"You said: {transcript or '[unrecognized]'}")
        print(f"Bot: {text}")
        if fallback:
            print(f"Fallback used: {fallback_reason or 'unknown'}")

        audio_b64 = str(reply.get("audio_base64", ""))
        if audio_b64:
            try:
                out_audio = base64.b64decode(audio_b64, validate=True)
                out_rate = int(reply.get("sample_rate_hz", sample_rate_hz))
            except Exception:
                print("Invalid audio payload in response; skipping playback.")
                continue
            if not play_audio(out_audio, sample_rate_hz=out_rate):
                print("Audio playback failed.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local mic/speaker voice console against CallCentreVoiceBot API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--sample-rate-hz", type=int, default=16000)
    parser.add_argument("--duration-seconds", type=int, default=4)
    args = parser.parse_args()

    return run_console(base_url=args.base_url.rstrip("/"), sample_rate_hz=args.sample_rate_hz, duration_seconds=args.duration_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
