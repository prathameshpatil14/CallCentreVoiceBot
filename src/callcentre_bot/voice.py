from __future__ import annotations

from dataclasses import dataclass
import math
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path


@dataclass
class AudioChunk:
    pcm16_bytes: bytes
    sample_rate_hz: int = 16000


@dataclass(frozen=True)
class StageSLO:
    stage: str
    max_latency_ms: int


VOICE_PIPELINE_SLOS = [
    StageSLO("asr", 350),
    StageSLO("nlu", 80),
    StageSLO("policy", 60),
    StageSLO("tts", 400),
]


class VoiceActivityDetector:
    def is_speech(self, audio: AudioChunk, threshold: int = 400) -> bool:
        if not audio.pcm16_bytes:
            return False
        samples = [int.from_bytes(audio.pcm16_bytes[i : i + 2], "little", signed=True) for i in range(0, len(audio.pcm16_bytes) - 1, 2)]
        avg = sum(abs(sample) for sample in samples) / max(1, len(samples))
        return avg >= threshold


class ASRAdapter:
    def transcribe(self, audio: AudioChunk, language_hint: str = "auto") -> str:
        raise NotImplementedError


class TTSAdapter:
    def synthesize(self, text: str, language: str = "en") -> AudioChunk:
        raise NotImplementedError


class OfflineASRAdapter(ASRAdapter):
    """Fallback decoder used only when production engines are unavailable."""

    def transcribe(self, audio: AudioChunk, language_hint: str = "auto") -> str:
        try:
            return audio.pcm16_bytes.decode("utf-8").strip()
        except UnicodeDecodeError:
            return ""


class LocalWhisperCppASRAdapter(ASRAdapter):
    """Production ASR using local whisper.cpp CLI binary."""

    def __init__(self, command: str) -> None:
        self.command = command
        if not shutil.which(command):
            raise RuntimeError(f"ASR command not found: {command}")

    def transcribe(self, audio: AudioChunk, language_hint: str = "auto") -> str:
        with tempfile.TemporaryDirectory(prefix="voice_asr_") as tmp:
            wav_path = Path(tmp) / "input.wav"
            _write_wav(wav_path, audio)
            cmd = [
                self.command,
                "-f",
                str(wav_path),
                "-nt",
                "-of",
                str(Path(tmp) / "transcript"),
            ]
            if language_hint and language_hint != "auto":
                cmd += ["-l", language_hint]
            completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                return ""

            txt_path = Path(tmp) / "transcript.txt"
            if txt_path.exists():
                return txt_path.read_text(encoding="utf-8").strip()
            return completed.stdout.strip()


class OfflineTTSAdapter(TTSAdapter):
    """Fallback tone generator used when production TTS is unavailable."""

    def synthesize(self, text: str, language: str = "en") -> AudioChunk:
        duration_seconds = min(3, max(1, len(text) // 40 + 1))
        sample_rate = 16000
        frequency = 220.0
        total_samples = duration_seconds * sample_rate
        pcm = bytearray()
        for i in range(total_samples):
            value = int(1200 * math.sin(2 * math.pi * frequency * (i / sample_rate)))
            pcm += int(value).to_bytes(2, "little", signed=True)
        return AudioChunk(bytes(pcm), sample_rate_hz=sample_rate)


class LocalPiperTTSAdapter(TTSAdapter):
    """Production TTS using local piper binary and local model file."""

    def __init__(self, command: str, model_path: str, multilingual_models: dict[str, str] | None = None) -> None:
        self.command = command
        self.model_path = model_path
        self.multilingual_models = multilingual_models or {}
        if not shutil.which(command):
            raise RuntimeError(f"TTS command not found: {command}")
        if not model_path or not Path(model_path).exists():
            raise RuntimeError("PIPER_MODEL_PATH must point to a valid local model file")
        for language, path in self.multilingual_models.items():
            if path and not Path(path).exists():
                raise RuntimeError(f"TTS model for {language} not found at {path}")

    def synthesize(self, text: str, language: str = "en") -> AudioChunk:
        with tempfile.TemporaryDirectory(prefix="voice_tts_") as tmp:
            out_wav = Path(tmp) / "speech.wav"
            selected_model = self.multilingual_models.get(language) or self.model_path
            cmd = [
                self.command,
                "--model",
                selected_model,
                "--output_file",
                str(out_wav),
            ]
            completed = subprocess.run(cmd, input=text, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                raise RuntimeError(f"piper failed: {completed.stderr.strip()}")
            return _read_wav(out_wav)


class DomainLanguageModel:
    def score(self, text: str) -> float:
        return min(1.0, max(0.0, len(text.split()) / 20))


class ProsodyController:
    def style_for_intent(self, intent: str) -> str:
        if intent in {"sales", "upsell"}:
            return "energetic_warm"
        if intent in {"support", "refund"}:
            return "calm_empathic"
        return "neutral"


def build_asr_adapter(mode: str, whisper_command: str, fallback_enabled: bool) -> ASRAdapter:
    if mode in {"auto", "production"}:
        try:
            return LocalWhisperCppASRAdapter(whisper_command)
        except RuntimeError:
            if not fallback_enabled:
                raise
    return OfflineASRAdapter()


def build_tts_adapter(
    mode: str,
    piper_command: str,
    piper_model_path: str,
    fallback_enabled: bool,
    multilingual_models: dict[str, str] | None = None,
) -> TTSAdapter:
    if mode in {"auto", "production"}:
        try:
            return LocalPiperTTSAdapter(piper_command, piper_model_path, multilingual_models=multilingual_models)
        except RuntimeError:
            if not fallback_enabled:
                raise
    return OfflineTTSAdapter()


def _write_wav(path: Path, audio: AudioChunk) -> None:
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(audio.sample_rate_hz)
        wav_file.writeframes(audio.pcm16_bytes)


def _read_wav(path: Path) -> AudioChunk:
    with wave.open(str(path), "rb") as wav_file:
        sample_width = wav_file.getsampwidth()
        channels = wav_file.getnchannels()
        if sample_width != 2 or channels != 1:
            raise RuntimeError("TTS output must be mono PCM16 wav")
        frames = wav_file.readframes(wav_file.getnframes())
        return AudioChunk(pcm16_bytes=frames, sample_rate_hz=wav_file.getframerate())
