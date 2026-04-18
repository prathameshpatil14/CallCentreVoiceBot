from dataclasses import dataclass
import math


@dataclass
class AudioChunk:
    pcm16_bytes: bytes
    sample_rate_hz: int = 16000


class VoiceActivityDetector:
    def is_speech(self, audio: AudioChunk, threshold: int = 400) -> bool:
        if not audio.pcm16_bytes:
            return False
        samples = [int.from_bytes(audio.pcm16_bytes[i : i + 2], "little", signed=True) for i in range(0, len(audio.pcm16_bytes) - 1, 2)]
        avg = sum(abs(sample) for sample in samples) / max(1, len(samples))
        return avg >= threshold


class ASRAdapter:
    def transcribe(self, audio: AudioChunk) -> str:
        raise NotImplementedError


class TTSAdapter:
    def synthesize(self, text: str) -> AudioChunk:
        raise NotImplementedError


class OfflineASRAdapter(ASRAdapter):
    """Simple in-house placeholder decoder.

    Expected input for now is utf-8 encoded bytes from upstream capture service.
    """

    def transcribe(self, audio: AudioChunk) -> str:
        try:
            return audio.pcm16_bytes.decode("utf-8").strip()
        except UnicodeDecodeError:
            return ""


class OfflineTTSAdapter(TTSAdapter):
    """Simple in-house tone generator placeholder (not natural speech)."""

    def synthesize(self, text: str) -> AudioChunk:
        duration_seconds = min(3, max(1, len(text) // 40 + 1))
        sample_rate = 16000
        frequency = 220.0
        total_samples = duration_seconds * sample_rate
        pcm = bytearray()
        for i in range(total_samples):
            value = int(1200 * math.sin(2 * math.pi * frequency * (i / sample_rate)))
            pcm += int(value).to_bytes(2, "little", signed=True)
        return AudioChunk(bytes(pcm), sample_rate_hz=sample_rate)
