from dataclasses import dataclass


@dataclass
class AudioChunk:
    pcm16_bytes: bytes


class ASRAdapter:
    """Replace with real speech-to-text provider in production."""

    def transcribe(self, _: AudioChunk) -> str:
        raise NotImplementedError


class TTSAdapter:
    """Replace with real text-to-speech provider in production."""

    def synthesize(self, _: str) -> AudioChunk:
        raise NotImplementedError
